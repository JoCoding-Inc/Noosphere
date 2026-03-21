from __future__ import annotations
import asyncio
import contextlib
import json
import logging
import os
import signal

import redis as _redis_sync

from backend.celery_app import celery_app, REDIS_URL
from backend.db import (
    save_sim_results,
    update_simulation_status,
    DB_PATH,
    mark_simulation_started,
    touch_simulation_heartbeat,
    simulation_cancel_requested,
)

logger = logging.getLogger(__name__)

STREAM_KEY = "sim_stream:{}"
STREAM_TTL = 7200   # 2시간 후 자동 만료
STREAM_MAXLEN = 2000
TASK_HEARTBEAT_INTERVAL = float(os.getenv("SIM_TASK_HEARTBEAT_INTERVAL", "5"))
TASK_CANCEL_POLL_INTERVAL = float(os.getenv("SIM_TASK_CANCEL_POLL_INTERVAL", "1"))
USER_CANCEL_MESSAGE = "Cancelled by user"


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

        main_task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        installed_signal_handlers: list[int] = []

        def request_cancel(reason: str) -> None:
            if main_task is not None and not main_task.done():
                main_task.cancel(reason)

        def handle_signal(sig: int) -> None:
            sig_name = signal.Signals(sig).name
            logger.warning("Simulation %s received %s", sim_id, sig_name)
            request_cancel(f"Received {sig_name}")

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, handle_signal, sig)
                installed_signal_handlers.append(sig)
            except (NotImplementedError, RuntimeError, ValueError):
                continue

        async def checkpoint() -> None:
            if await asyncio.to_thread(simulation_cancel_requested, DB_PATH, sim_id):
                raise asyncio.CancelledError(USER_CANCEL_MESSAGE)

        async def cancellation_watcher() -> None:
            while True:
                if await asyncio.to_thread(simulation_cancel_requested, DB_PATH, sim_id):
                    logger.info("Simulation %s cancellation watcher requested stop", sim_id)
                    request_cancel(USER_CANCEL_MESSAGE)
                    return
                await asyncio.sleep(TASK_CANCEL_POLL_INTERVAL)

        async def heartbeat_loop() -> None:
            while True:
                alive = await asyncio.to_thread(touch_simulation_heartbeat, DB_PATH, sim_id)
                if not alive:
                    logger.info("Simulation %s heartbeat loop detected inactive state", sim_id)
                    request_cancel(USER_CANCEL_MESSAGE)
                    return
                await asyncio.sleep(TASK_HEARTBEAT_INTERVAL)

        watcher_task: asyncio.Task | None = None
        heartbeat_task: asyncio.Task | None = None
        analysis_md = ""
        posts_by_platform: dict = {}
        personas_by_platform: dict = {}
        report_json: dict = {}
        report_md: str = ""

        try:
            if not await asyncio.to_thread(mark_simulation_started, DB_PATH, sim_id):
                logger.info("Simulation %s will not start because it is no longer active", sim_id)
                return

            provider = config.get("provider", "openai")
            from backend import llm as _llm
            try:
                _llm.check_provider_key(provider)
            except ValueError as e:
                publish({"type": "sim_error", "message": str(e)})
                return

            watcher_task = asyncio.create_task(cancellation_watcher())
            heartbeat_task = asyncio.create_task(heartbeat_loop())
            await checkpoint()
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
                provider=provider,
            )
            await checkpoint()
            domain_str = await detect_domain(config["input_text"], provider=provider)

            publish({
                "type": "sim_progress",
                "message": f"Domain: {domain_str}. Generating analysis report...",
            })
            analysis_md = await generate_analysis_report(
                raw_items=raw_items,
                domain=domain_str,
                input_text=config["input_text"],
                language=config["language"],
                provider=provider,
            )
            await checkpoint()
            publish({"type": "sim_analysis", "data": {"markdown": analysis_md}})

            context_nodes = [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "source": item["source"],
                    "abstract": item.get("text") or item.get("title", ""),
                }
                for item in raw_items[:30]
            ] or [{
                "id": "input",
                "title": config["input_text"][:80],
                "source": "input_text",
                "abstract": config["input_text"][:300],
            }]

            publish({
                "type": "sim_progress",
                "message": f"Starting simulation with {len(context_nodes)} context nodes...",
            })

            async for event in run_simulation(
                input_text=config["input_text"],
                context_nodes=context_nodes,
                domain=domain_str,
                max_agents=config["max_agents"],
                num_rounds=config["num_rounds"],
                platforms=config["platforms"],
                language=config["language"],
                activation_rate=config["activation_rate"],
                provider=provider,
            ):
                await checkpoint()
                if event["type"] == "sim_report":
                    data = event["data"]
                    posts_by_platform = data.get("platform_states", {})
                    personas_by_platform = data.get("personas", {})
                    report_json = data.get("report_json", {})
                    report_md = data.get("markdown", "")
                publish(event)

            await checkpoint()
            save_sim_results(
                DB_PATH,
                sim_id,
                posts_by_platform,
                personas_by_platform,
                report_json,
                report_md,
                analysis_md=analysis_md,
            )
            if not await asyncio.to_thread(
                update_simulation_status,
                DB_PATH,
                sim_id,
                "completed",
                allowed_current_statuses={"running"},
                require_not_cancelled=True,
            ):
                logger.info(
                    "Simulation %s reached completion after its status changed; leaving DB status untouched",
                    sim_id,
                )
        except asyncio.CancelledError:
            logger.info("Simulation %s cancelled", sim_id)
            publish({"type": "sim_error", "message": USER_CANCEL_MESSAGE})
            await asyncio.to_thread(
                update_simulation_status,
                DB_PATH,
                sim_id,
                "failed",
                allowed_current_statuses={"running"},
            )
        except Exception as exc:
            logger.error("Simulation %s failed: %s", sim_id, exc, exc_info=True)
            publish({"type": "sim_error", "message": str(exc)})
            await asyncio.to_thread(
                update_simulation_status,
                DB_PATH,
                sim_id,
                "failed",
                allowed_current_statuses={"running"},
            )
        finally:
            for task in (watcher_task, heartbeat_task):
                if task is not None:
                    task.cancel()
            for task in (watcher_task, heartbeat_task):
                if task is None:
                    continue
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            for sig in installed_signal_handlers:
                with contextlib.suppress(Exception):
                    loop.remove_signal_handler(sig)
            publish({"type": "sim_done"})
            r.expire(stream_key, STREAM_TTL)

    try:
        asyncio.run(_run())
    finally:
        r.close()
