from __future__ import annotations
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from backend.celery_app import REDIS_URL
from backend.db import (
    init_db, create_simulation, update_simulation_status,
    get_sim_results, list_history, get_simulation, DB_PATH,
    count_active_simulations, reconcile_stale_simulations, request_simulation_cancel,
    get_checkpoint,
)
from backend.tasks import run_simulation_task, STREAM_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_JOBS = int(os.getenv("MAX_JOBS", "5"))
SIM_QUEUE_TIMEOUT_SECONDS = int(os.getenv("SIM_QUEUE_TIMEOUT_SECONDS", "900"))
SIM_HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("SIM_HEARTBEAT_TIMEOUT_SECONDS", "90"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DB_PATH)
    stale_count = reconcile_stale_simulations(
        DB_PATH,
        queue_timeout_seconds=SIM_QUEUE_TIMEOUT_SECONDS,
        heartbeat_timeout_seconds=SIM_HEARTBEAT_TIMEOUT_SECONDS,
    )
    if stale_count:
        logger.info("Marked %d stale simulations as failed", stale_count)
    yield


app = FastAPI(title="Noosphere v2", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimConfig(BaseModel):
    input_text: str
    language: str = "English"
    num_rounds: int = 12
    max_agents: int = 50
    platforms: list[str] = ["hackernews", "producthunt", "indiehackers", "reddit_startups", "linkedin"]
    activation_rate: float = 0.25
    source_limits: dict[str, int] = {}
    provider: str = "openai"

    @field_validator("input_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("input_text must not be empty")
        return v.strip()

    @field_validator("activation_rate")
    @classmethod
    def rate_valid(cls, v: float) -> float:
        if not (0.1 <= v <= 1.0):
            raise ValueError("activation_rate must be between 0.1 and 1.0")
        return v

    @field_validator("num_rounds")
    @classmethod
    def rounds_valid(cls, v: int) -> int:
        return max(1, min(v, 30))

    @field_validator("max_agents")
    @classmethod
    def agents_valid(cls, v: int) -> int:
        return max(1, min(v, 150))

    @field_validator("provider")
    @classmethod
    def provider_valid(cls, v: str) -> str:
        if v not in {"openai", "anthropic", "gemini"}:
            raise ValueError("provider must be openai, anthropic, or gemini")
        return v


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/simulate")
async def simulate(config: SimConfig):
    """Start a simulation via Celery worker. Returns sim_id for streaming."""
    reconcile_stale_simulations(
        DB_PATH,
        queue_timeout_seconds=SIM_QUEUE_TIMEOUT_SECONDS,
        heartbeat_timeout_seconds=SIM_HEARTBEAT_TIMEOUT_SECONDS,
    )
    running_count = count_active_simulations(
        DB_PATH,
        queue_timeout_seconds=SIM_QUEUE_TIMEOUT_SECONDS,
        heartbeat_timeout_seconds=SIM_HEARTBEAT_TIMEOUT_SECONDS,
    )
    if running_count >= MAX_JOBS:
        raise HTTPException(429, "Too many concurrent simulations")

    sim_id = str(uuid.uuid4())
    create_simulation(DB_PATH, sim_id, config.input_text, config.language,
                      config.model_dump(), "")

    try:
        run_simulation_task.apply_async(args=[sim_id, config.model_dump()], task_id=sim_id)
    except Exception:
        update_simulation_status(DB_PATH, sim_id, "failed", allowed_current_statuses={"running"})
        raise
    return {"sim_id": sim_id}


@app.get("/simulate-stream/{sim_id}")
async def simulate_stream(sim_id: str, request: Request, last_id: str = "0"):
    """SSE stream backed by Redis Streams.
    last_id: Redis stream ID to resume from (pass "0" to replay all, omit for default).
    """
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")

    stream_key = STREAM_KEY.format(sim_id)
    start_id = last_id or "0"

    async def event_generator():
        r = aioredis.from_url(REDIS_URL, decode_responses=True)
        current_id = start_id
        try:
            while True:
                results = await r.xread({stream_key: current_id}, count=100, block=30_000)
                if not results:
                    yield 'data: {"type":"heartbeat"}\n\n'
                    continue
                for _stream_name, messages in results:
                    for msg_id, fields in messages:
                        current_id = msg_id
                        raw = fields["data"]
                        yield f"id: {msg_id}\ndata: {raw}\n\n"
                        if json.loads(raw).get("type") == "sim_done":
                            return
        except Exception:
            return
        finally:
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/results/{sim_id}")
async def get_results(sim_id: str):
    results = get_sim_results(DB_PATH, sim_id)
    if not results:
        raise HTTPException(404, "Results not found")
    return results


@app.get("/simulate/{sim_id}/status")
async def simulation_status(sim_id: str):
    """Return current simulation status and last checkpointed round."""
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    checkpoint = get_checkpoint(DB_PATH, sim_id)
    return {
        "status": sim["status"],
        "last_round": checkpoint["last_round"] if checkpoint else 0,
    }


@app.post("/simulate/{sim_id}/resume")
async def resume_simulation(sim_id: str):
    """Resume a failed simulation from its last checkpoint."""
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    if sim["status"] != "failed":
        raise HTTPException(400, f"Only failed simulations can be resumed (status: {sim['status']})")
    checkpoint = get_checkpoint(DB_PATH, sim_id)
    if not checkpoint:
        raise HTTPException(409, "No checkpoint available; start a new simulation")

    # Check concurrency limit (same as /simulate endpoint)
    reconcile_stale_simulations(
        DB_PATH,
        queue_timeout_seconds=SIM_QUEUE_TIMEOUT_SECONDS,
        heartbeat_timeout_seconds=SIM_HEARTBEAT_TIMEOUT_SECONDS,
    )
    running_count = count_active_simulations(
        DB_PATH,
        queue_timeout_seconds=SIM_QUEUE_TIMEOUT_SECONDS,
        heartbeat_timeout_seconds=SIM_HEARTBEAT_TIMEOUT_SECONDS,
    )
    if running_count >= MAX_JOBS:
        raise HTTPException(429, "Too many concurrent simulations")

    # Atomic guard: only succeeds if status is still 'failed'
    updated = update_simulation_status(
        DB_PATH, sim_id, "running",
        allowed_current_statuses={"failed"},
    )
    if not updated:
        raise HTTPException(409, "Simulation state changed; try again")

    config = json.loads(sim["config_json"])
    resume_task_id = str(uuid.uuid4())
    try:
        run_simulation_task.apply_async(args=[sim_id, config], task_id=resume_task_id)
    except Exception:
        update_simulation_status(DB_PATH, sim_id, "failed", allowed_current_statuses={"running"})
        raise

    return {"sim_id": sim_id, "resuming_from_round": checkpoint["last_round"] + 1}


@app.get("/history")
async def history():
    return list_history(DB_PATH)


@app.post("/simulate/{sim_id}/cancel")
async def cancel_simulation(sim_id: str):
    """Cancel a running simulation: mark DB cancelled first, then revoke worker task."""
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    if sim["status"] != "running":
        raise HTTPException(400, f"Simulation is not running (status: {sim['status']})")

    if not request_simulation_cancel(DB_PATH, sim_id):
        raise HTTPException(409, "Simulation state changed before cancellation")

    # Celery task revoke (terminate=True sends SIGTERM to the worker child in prefork pools)
    from backend.celery_app import celery_app as _celery
    try:
        _celery.control.revoke(sim_id, terminate=True, signal="SIGTERM")
    except Exception:
        logger.exception("Failed to revoke simulation %s; relying on cooperative cancellation", sim_id)

    # Redis stream에 종료 이벤트 발행 (SSE 클라이언트가 연결 끊도록)
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    stream_key = STREAM_KEY.format(sim_id)
    try:
        await r.xadd(stream_key, {"data": json.dumps({"type": "sim_error", "message": "Cancelled by user"})})
        await r.xadd(stream_key, {"data": json.dumps({"type": "sim_done"})})
    finally:
        await r.aclose()

    return {"status": "cancelled"}



@app.get("/export/{sim_id}")
async def export_pdf(sim_id: str):
    """Generate and return PDF report."""
    results = get_sim_results(DB_PATH, sim_id)
    if not results:
        raise HTTPException(404, "Results not found")
    sim = get_simulation(DB_PATH, sim_id)

    from backend.exporter import build_pdf
    import json as _json
    sim_params = _json.loads(sim["config_json"]) if sim else {}
    pdf_bytes = await build_pdf(
        report_md=results["report_md"],
        input_text=sim["input_text"] if sim else "",
        sim_id=sim_id,
        domain=sim["domain"] if sim else "",
        language=sim["language"] if sim else "English",
        analysis_md=results.get("analysis_md"),
        sim_params=sim_params,
        final_report_md=results.get("final_report_md"),
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="noosphere-report-{sim_id[:8]}.pdf"'},
    )
