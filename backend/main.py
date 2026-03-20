from __future__ import annotations
import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator

from backend.db import (
    init_db, create_simulation, update_simulation_status,
    save_sim_results, get_sim_results, list_history, get_simulation, DB_PATH
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_JOBS = int(os.getenv("MAX_JOBS", "5"))
_sim_jobs: dict[str, dict] = {}  # sim_id → {"queue": asyncio.Queue, "created_at": float}
_sim_jobs_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DB_PATH)
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/simulate")
async def simulate(config: SimConfig):
    """Start a simulation. Returns sim_id for streaming."""
    async with _sim_jobs_lock:
        running = sum(1 for j in _sim_jobs.values()
                      if time.time() - j["created_at"] < 1800)
        if running >= MAX_JOBS:
            raise HTTPException(429, "Too many concurrent simulations")

    sim_id = str(uuid.uuid4())
    domain = ""  # will be detected during run
    create_simulation(DB_PATH, sim_id, config.input_text, config.language,
                      config.model_dump(), domain)

    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    async with _sim_jobs_lock:
        _sim_jobs[sim_id] = {"queue": queue, "created_at": time.time()}

    async def run():
        from backend.analyzer import analyze
        from backend.context_builder import detect_domain
        from backend.reporter import generate_analysis_report
        from backend.simulation.social_runner import run_simulation

        try:
            # Phase 1: 소스 검색 + 분석 보고서
            queue.put_nowait({"type": "sim_progress", "message": "Searching external sources..."})
            raw_items = await analyze(config.input_text, limits=config.source_limits or None)
            domain_str = await detect_domain(config.input_text)

            queue.put_nowait({"type": "sim_progress",
                              "message": f"Domain: {domain_str}. Generating analysis report..."})
            analysis_md = await generate_analysis_report(
                raw_items=raw_items,
                domain=domain_str,
                input_text=config.input_text,
                language=config.language,
            )
            queue.put_nowait({"type": "sim_analysis", "data": {"markdown": analysis_md}})

            # Phase 2: RawItems → context nodes for simulation
            context_nodes = [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "source": item["source"],
                    "abstract": item.get("text") or item.get("title", ""),
                }
                for item in raw_items[:30]
            ] or [{"id": "input", "title": config.input_text[:80],
                   "source": "input_text", "abstract": config.input_text[:300]}]

            queue.put_nowait({"type": "sim_progress",
                              "message": f"Starting simulation with {len(context_nodes)} context nodes..."})

            posts_by_platform: dict = {}
            personas_by_platform: dict = {}
            report_json: dict = {}
            report_md: str = ""

            async for event in run_simulation(
                input_text=config.input_text,
                context_nodes=context_nodes,
                domain=domain_str,
                max_agents=config.max_agents,
                num_rounds=config.num_rounds,
                platforms=config.platforms,
                language=config.language,
                activation_rate=config.activation_rate,
            ):
                if event["type"] == "sim_report":
                    data = event["data"]
                    posts_by_platform = data.get("platform_states", {})
                    personas_by_platform = data.get("personas", {})
                    report_json = data.get("report_json", {})
                    report_md = data.get("markdown", "")
                queue.put_nowait(event)

            save_sim_results(DB_PATH, sim_id, posts_by_platform,
                             personas_by_platform, report_json, report_md,
                             analysis_md=analysis_md)
            update_simulation_status(DB_PATH, sim_id, "completed")

        except Exception as exc:
            logger.error("Simulation %s failed: %s", sim_id, exc)
            queue.put_nowait({"type": "sim_error", "message": str(exc)})
            update_simulation_status(DB_PATH, sim_id, "failed")
        finally:
            queue.put_nowait({"type": "sim_done"})
            queue.put_nowait(None)  # sentinel

    asyncio.create_task(run())
    return {"sim_id": sim_id}


@app.get("/simulate-stream/{sim_id}")
async def simulate_stream(sim_id: str):
    """SSE stream for a simulation job."""
    async with _sim_jobs_lock:
        job = _sim_jobs.get(sim_id)

    if not job:
        # Check DB — maybe already completed
        sim = get_simulation(DB_PATH, sim_id)
        if not sim:
            raise HTTPException(404, "Simulation not found")

    queue = job["queue"] if job else None

    async def event_generator():
        if queue is None:
            # Completed, stream results from DB
            results = get_sim_results(DB_PATH, sim_id)
            if results:
                yield f"data: {json.dumps({'type': 'sim_report', 'data': results})}\n\n"
            yield f"data: {json.dumps({'type': 'sim_done'})}\n\n"
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"heartbeat\"}\n\n"
                continue
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "sim_done":
                break

        async with _sim_jobs_lock:
            _sim_jobs.pop(sim_id, None)

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


@app.get("/history")
async def history():
    return list_history(DB_PATH)


@app.get("/export/{sim_id}")
async def export_pdf(sim_id: str):
    """Generate and return PDF report."""
    results = get_sim_results(DB_PATH, sim_id)
    if not results:
        raise HTTPException(404, "Results not found")
    sim = get_simulation(DB_PATH, sim_id)

    from backend.exporter import build_pdf
    pdf_bytes = await build_pdf(
        report_md=results["report_md"],
        input_text=sim["input_text"] if sim else "",
        sim_id=sim_id,
        domain=sim["domain"] if sim else "",
        language=sim["language"] if sim else "English",
        analysis_md=results.get("analysis_md"),
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="noosphere-report-{sim_id[:8]}.pdf"'},
    )
