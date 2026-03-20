from __future__ import annotations
import asyncio
import json
import logging
import os

import redis as _redis_sync

from backend.celery_app import celery_app, REDIS_URL
from backend.db import save_sim_results, update_simulation_status, DB_PATH

logger = logging.getLogger(__name__)

STREAM_KEY = "sim_stream:{}"
STREAM_TTL = 7200   # 2시간 후 자동 만료
STREAM_MAXLEN = 2000


@celery_app.task(bind=True, name="backend.tasks.run_simulation_task")
def run_simulation_task(self, sim_id: str, config: dict) -> None:
    r = _redis_sync.Redis.from_url(REDIS_URL, decode_responses=True)
    stream_key = STREAM_KEY.format(sim_id)

    def publish(event: dict) -> None:
        r.xadd(stream_key, {"data": json.dumps(event)}, maxlen=STREAM_MAXLEN)

    async def _run() -> None:
        from backend.analyzer import analyze
        from backend.context_builder import detect_domain
        from backend.reporter import generate_analysis_report
        from backend.simulation.social_runner import run_simulation

        analysis_md = ""
        posts_by_platform: dict = {}
        personas_by_platform: dict = {}
        report_json: dict = {}
        report_md: str = ""

        try:
            publish({"type": "sim_progress", "message": "Searching external sources..."})
            def on_source_done(source_name: str, items: list[dict]) -> None:
                for item in items:
                    title = item.get("title") or item.get("name") or ""
                    if not title:
                        continue
                    text = item.get("text") or item.get("abstract") or item.get("description") or ""
                    snippet = text[:140].rstrip() if text else ""
                    if snippet and len(text) > 140:
                        snippet += "…"
                    publish({
                        "type": "sim_source_item",
                        "source": source_name,
                        "title": title,
                        "snippet": snippet,
                    })

            raw_items = await analyze(
                config["input_text"],
                limits=config.get("source_limits") or None,
                on_source_done=on_source_done,
            )
            domain_str = await detect_domain(config["input_text"])

            publish({"type": "sim_progress",
                     "message": f"Domain: {domain_str}. Generating analysis report..."})
            analysis_md = await generate_analysis_report(
                raw_items=raw_items,
                domain=domain_str,
                input_text=config["input_text"],
                language=config["language"],
            )
            publish({"type": "sim_analysis", "data": {"markdown": analysis_md}})

            context_nodes = [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "source": item["source"],
                    "abstract": item.get("text") or item.get("title", ""),
                }
                for item in raw_items[:30]
            ] or [{"id": "input", "title": config["input_text"][:80],
                   "source": "input_text", "abstract": config["input_text"][:300]}]

            publish({"type": "sim_progress",
                     "message": f"Starting simulation with {len(context_nodes)} context nodes..."})

            async for event in run_simulation(
                input_text=config["input_text"],
                context_nodes=context_nodes,
                domain=domain_str,
                max_agents=config["max_agents"],
                num_rounds=config["num_rounds"],
                platforms=config["platforms"],
                language=config["language"],
                activation_rate=config["activation_rate"],
            ):
                if event["type"] == "sim_report":
                    data = event["data"]
                    posts_by_platform = data.get("platform_states", {})
                    personas_by_platform = data.get("personas", {})
                    report_json = data.get("report_json", {})
                    report_md = data.get("markdown", "")
                publish(event)

            save_sim_results(
                DB_PATH, sim_id,
                posts_by_platform, personas_by_platform,
                report_json, report_md,
                analysis_md=analysis_md,
            )
            update_simulation_status(DB_PATH, sim_id, "completed")

        except Exception as exc:
            logger.error("Simulation %s failed: %s", sim_id, exc, exc_info=True)
            publish({"type": "sim_error", "message": str(exc)})
            update_simulation_status(DB_PATH, sim_id, "failed")

        finally:
            publish({"type": "sim_done"})
            r.expire(stream_key, STREAM_TTL)

    asyncio.run(_run())
    r.close()
