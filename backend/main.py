from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional dependency in local dev only
    def load_dotenv() -> bool:
        return False

load_dotenv()

try:
    import redis.asyncio as aioredis
except ModuleNotFoundError:  # pragma: no cover - optional during config-only imports/tests
    aioredis = None

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
except ModuleNotFoundError:  # pragma: no cover - allow config imports without web deps
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class Request:
        pass

    class StreamingResponse:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class CORSMiddleware:
        pass

    class FastAPI:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def add_middleware(self, *args, **kwargs):
            return None

        def get(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def post(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def delete(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def put(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def patch(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

from pydantic import BaseModel, field_validator


try:
    from backend.celery_app import REDIS_URL
    from backend.db import (
        init_db, create_simulation, update_simulation_status,
        get_sim_results, list_history, get_simulation, DB_PATH,
        count_active_simulations, reconcile_stale_simulations, request_simulation_cancel,
        get_checkpoint, delete_simulation,
    )
    from backend.tasks import run_simulation_task, STREAM_KEY
except ModuleNotFoundError:  # pragma: no cover - allow SimConfig import in minimal envs
    REDIS_URL = ""
    DB_PATH = ""

    def _missing_dependency(*args, **kwargs):
        raise RuntimeError("Server dependencies are not installed")

    init_db = _missing_dependency
    create_simulation = _missing_dependency
    update_simulation_status = _missing_dependency
    get_sim_results = _missing_dependency
    list_history = _missing_dependency
    get_simulation = _missing_dependency
    count_active_simulations = _missing_dependency
    reconcile_stale_simulations = _missing_dependency
    request_simulation_cancel = _missing_dependency
    get_checkpoint = _missing_dependency

    class _MissingTask:
        def apply_async(self, *args, **kwargs):
            raise RuntimeError("Task queue dependencies are not installed")

    run_simulation_task = _MissingTask()
    STREAM_KEY = "sim_stream:{}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_JOBS = int(os.getenv("MAX_JOBS", "5"))
SIM_QUEUE_TIMEOUT_SECONDS = int(os.getenv("SIM_QUEUE_TIMEOUT_SECONDS", "900"))
SIM_HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("SIM_HEARTBEAT_TIMEOUT_SECONDS", "90"))
REDIS_STREAM_ID_RE = re.compile(r"^(0|\d+-\d+)$")


def _parse_allowed_origins(value: str | None) -> list[str]:
    origins = [origin.strip() for origin in (value or "*").split(",") if origin.strip()]
    return origins or ["*"]


_allowed_origins = _parse_allowed_origins(os.getenv("ALLOWED_ORIGINS"))


def _require_aioredis():
    if aioredis is None:
        raise HTTPException(503, "Redis client is not installed")
    return aioredis


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
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimConfig(BaseModel):
    input_text: str
    language: str = "English"
    num_rounds: int = 8
    max_agents: int = 150
    platforms: list[str] = ["hackernews", "producthunt", "indiehackers", "reddit_startups", "linkedin"]
    activation_rate: float = 0.25
    source_limits: dict[str, int] = {}
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
        return max(100, min(v, 200))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/simulate")
async def simulate(config: SimConfig, request: Request):
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
async def simulate_stream(sim_id: str, request: Request, last_id: str | None = None):
    """SSE stream backed by Redis Streams.
    last_id: Redis stream ID to resume from (pass "0" to replay all, omit for default).
    """
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    if last_id is not None and not REDIS_STREAM_ID_RE.fullmatch(last_id):
        raise HTTPException(400, "Invalid last_id")

    stream_key = STREAM_KEY.format(sim_id)
    start_id = last_id or "0"

    async def event_generator():
        redis_client = _require_aioredis()
        r = redis_client.from_url(REDIS_URL, decode_responses=True)
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
        "has_checkpoint": checkpoint is not None,
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
    config["max_agents"] = max(100, min(config.get("max_agents", 150), 200))
    try:
        run_simulation_task.apply_async(args=[sim_id, config], task_id=sim_id)
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
    redis_client = _require_aioredis()
    r = redis_client.from_url(REDIS_URL, decode_responses=True)
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
    context_nodes = results.get("context_nodes_json") or []
    idea_node = next((n for n in context_nodes if isinstance(n, dict) and n.get("id") == "idea"), None)
    idea_title = idea_node.get("title", "") if idea_node else ""
    pdf_bytes = await build_pdf(
        report_md=results["report_md"],
        input_text=sim["input_text"] if sim else "",
        sim_id=sim_id,
        domain=sim["domain"] if sim else "",
        language=sim["language"] if sim else "English",
        analysis_md=results.get("analysis_md"),
        sim_params=sim_params,
        final_report_md=results.get("final_report_md"),
        idea_title=idea_title,
        gtm_md=results.get("gtm_md"),
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="noosphere-report-{sim_id[:8]}.pdf"'},
    )


@app.delete("/simulate/{sim_id}")
async def delete_simulation_endpoint(sim_id: str):
    """시뮬레이션 데이터를 DB와 Redis에서 완전 삭제."""
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    if sim.get("status") == "running":
        raise HTTPException(409, "Cannot delete a running simulation. Stop it first.")

    deleted = await asyncio.to_thread(delete_simulation, DB_PATH, sim_id)
    if not deleted:
        raise HTTPException(404, "Simulation not found")

    # Redis 스트림 키 삭제
    try:
        import redis as _redis_sync
        r = _redis_sync.from_url(REDIS_URL)
        r.delete(STREAM_KEY.format(sim_id))
        r.close()
    except Exception:
        pass  # Redis 삭제 실패는 무시 (이미 만료됐을 수 있음)

    return {"deleted": sim_id}
