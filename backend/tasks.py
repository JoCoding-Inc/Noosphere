from __future__ import annotations
import asyncio
import contextlib
import json
import logging
import os
import signal
from collections.abc import Callable

import redis as _redis_sync

from backend.celery_app import celery_app, REDIS_URL
from backend.db import (
    save_sim_results,
    update_simulation_status,
    DB_PATH,
    mark_simulation_started,
    touch_simulation_heartbeat,
    simulation_cancel_requested,
    save_checkpoint,
    get_checkpoint,
    delete_checkpoint,
)

logger = logging.getLogger(__name__)

import re as _re

_STOPWORDS = {
    'the', 'a', 'an', 'of', 'in', 'for', 'and', 'or', 'to', 'is', 'are',
    'with', 'on', 'at', 'by', 'as', 'from', 'that', 'this', 'it', 'be',
    'was', 'were', 'has', 'have', 'had', 'not', 'but', 'its', 'can', 'may',
    'will', 'we', 'our', 'their', 'they', 'which', 'who', 'how', 'what',
    'using', 'used', 'use', 'based', 'paper', 'model', 'data', 'results',
    'new', 'method', 'approach', 'show', 'propose', 'present', 'also',
    'one', 'two', 'three', 'large', 'high', 'low', 'via', 'into', 'over',
}

_DOMAIN_TYPES = {"tech", "research", "consumer", "business", "healthcare", "general"}
_TECH_AREAS = {"AI/ML", "cloud", "security", "data", "mobile", "web", "hardware", "other"}
_MARKETS = {"B2B", "B2C", "enterprise", "developer", "consumer", "academic"}
_PROBLEM_DOMAINS = {
    "automation", "analytics", "communication", "productivity",
    "infrastructure", "security", "UX", "compliance",
}


def _coerce_enum(value: object, allowed: set[str]) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text in allowed:
        return text
    lowered = text.lower()
    for option in allowed:
        if option.lower() == lowered:
            return option
    return ""


def _coerce_string_list(
    value: object,
    *,
    allowed: set[str] | None = None,
    max_items: int | None = None,
) -> list[str]:
    if isinstance(value, str):
        raw_items = [part.strip() for part in _re.split(r"[,;\n|]+", value) if part.strip()]
    elif isinstance(value, list):
        raw_items = [str(part).strip() for part in value if str(part).strip()]
    else:
        raw_items = []

    seen: set[str] = set()
    items: list[str] = []
    for item in raw_items:
        normalized = item
        if allowed is not None:
            normalized = _coerce_enum(item, allowed)
            if not normalized:
                continue
        dedupe_key = normalized.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(normalized)
        if max_items is not None and len(items) >= max_items:
            break
    return items


def _normalize_structured_payload(payload: object, fallback_summary: str) -> dict:
    data = payload if isinstance(payload, dict) else {}
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = fallback_summary
    else:
        summary = summary.strip()

    return {
        "summary": summary,
        "domain_type": _coerce_enum(data.get("domain_type"), _DOMAIN_TYPES),
        "tech_area": _coerce_string_list(data.get("tech_area"), allowed=_TECH_AREAS, max_items=2),
        "market": _coerce_string_list(data.get("market"), allowed=_MARKETS, max_items=2),
        "problem_domain": _coerce_string_list(data.get("problem_domain"), allowed=_PROBLEM_DOMAINS, max_items=2),
        "keywords": _coerce_string_list(data.get("keywords"), max_items=10),
        "entities": _coerce_string_list(data.get("entities"), max_items=10),
    }


def _normalized_token_set(value: object) -> set[str]:
    return {item.lower() for item in _coerce_string_list(value)}


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, excluding stopwords."""
    words = _re.findall(r'\b[a-z][a-z0-9]{2,}\b', text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _build_keyword_edges(nodes: list[dict], min_overlap: int = 2) -> list[dict]:
    """Build edges between nodes that share at least min_overlap keywords."""
    kw_map = {
        n['id']: _extract_keywords(f"{n.get('title', '')} {n.get('abstract', '')}")
        for n in nodes if n.get('id')
    }
    ids = list(kw_map.keys())
    edges: list[dict] = []
    for i, src in enumerate(ids):
        for tgt in ids[i + 1:]:
            overlap = len(kw_map[src] & kw_map[tgt])
            if overlap >= min_overlap:
                edges.append({'source': src, 'target': tgt, 'weight': overlap})
    return edges


def _build_structured_edges(nodes: list[dict], min_score: int = 2) -> list[dict]:
    """구조화 필드 기반 가중 엣지 빌딩."""
    edges: list[dict] = []
    node_list = [n for n in nodes if n.get("id")]
    for i, src in enumerate(node_list):
        for tgt in node_list[i + 1:]:
            score = 0
            # entities × 3
            src_entities = _normalized_token_set(src.get("_entities"))
            tgt_entities = _normalized_token_set(tgt.get("_entities"))
            score += len(src_entities & tgt_entities) * 3
            # keywords × 2
            src_kw = _normalized_token_set(src.get("_keywords"))
            tgt_kw = _normalized_token_set(tgt.get("_keywords"))
            score += len(src_kw & tgt_kw) * 2
            # domain_type × 1
            src_domain = _coerce_enum(src.get("_domain_type"), _DOMAIN_TYPES)
            tgt_domain = _coerce_enum(tgt.get("_domain_type"), _DOMAIN_TYPES)
            if src_domain and src_domain == tgt_domain:
                score += 1
            # tech_area × 1
            score += len(
                set(_coerce_string_list(src.get("_tech_area"), allowed=_TECH_AREAS))
                & set(_coerce_string_list(tgt.get("_tech_area"), allowed=_TECH_AREAS))
            )
            # market × 1
            score += len(
                set(_coerce_string_list(src.get("_market"), allowed=_MARKETS))
                & set(_coerce_string_list(tgt.get("_market"), allowed=_MARKETS))
            )
            # problem_domain × 1
            score += len(
                set(_coerce_string_list(src.get("_problem_domain"), allowed=_PROBLEM_DOMAINS))
                & set(_coerce_string_list(tgt.get("_problem_domain"), allowed=_PROBLEM_DOMAINS))
            )

            if score >= min_score:
                # label: most meaningful shared field
                shared_ents = list(src_entities & tgt_entities)[:2]
                if shared_ents:
                    label = " · ".join(sorted(shared_ents)[:2])
                else:
                    shared_kws = list(src_kw & tgt_kw)[:2]
                    if shared_kws:
                        label = " · ".join(sorted(shared_kws)[:2])
                    else:
                        tax_overlaps = []
                        if src.get("_domain_type") and src.get("_domain_type") == tgt.get("_domain_type"):
                            tax_overlaps.append(src["_domain_type"])
                        tax_overlaps += list(set(src.get("_tech_area") or []) & set(tgt.get("_tech_area") or []))
                        tax_overlaps += list(set(src.get("_market") or []) & set(tgt.get("_market") or []))
                        tax_overlaps += list(set(src.get("_problem_domain") or []) & set(tgt.get("_problem_domain") or []))
                        label = " · ".join(tax_overlaps[:2])
                edges.append({"source": src["id"], "target": tgt["id"], "weight": score, "label": label})
    return edges


def _calc_edges_for_node(new_node: dict, existing_nodes: list[dict], min_score: int = 2) -> list[dict]:
    """새 노드 1개와 기존 노드 목록 간의 엣지만 계산한다."""
    if not new_node.get("id"):
        return []
    edges: list[dict] = []
    src = new_node
    src_entities = set(src.get("_entities") or [])
    src_kw = set(src.get("_keywords") or [])
    for tgt in existing_nodes:
        if not tgt.get("id"):
            continue
        score = 0
        tgt_entities = set(tgt.get("_entities") or [])
        tgt_kw = set(tgt.get("_keywords") or [])
        score += len(src_entities & tgt_entities) * 3
        score += len(src_kw & tgt_kw) * 2
        if src.get("_domain_type") and src.get("_domain_type") == tgt.get("_domain_type"):
            score += 1
        score += len(set(src.get("_tech_area") or []) & set(tgt.get("_tech_area") or [])) * 1
        score += len(set(src.get("_market") or []) & set(tgt.get("_market") or [])) * 1
        score += len(set(src.get("_problem_domain") or []) & set(tgt.get("_problem_domain") or [])) * 1
        if score < min_score:
            continue
        # label 생성
        shared_ents = sorted(src_entities & tgt_entities)[:2]
        if shared_ents:
            label = " · ".join(shared_ents[:2])
        else:
            shared_kws = sorted(src_kw & tgt_kw)[:2]
            if shared_kws:
                label = " · ".join(shared_kws[:2])
            else:
                tax_overlaps = []
                if src.get("_domain_type") and src.get("_domain_type") == tgt.get("_domain_type"):
                    tax_overlaps.append(src["_domain_type"])
                tax_overlaps += list(set(src.get("_tech_area") or []) & set(tgt.get("_tech_area") or []))
                tax_overlaps += list(set(src.get("_market") or []) & set(tgt.get("_market") or []))
                tax_overlaps += list(set(src.get("_problem_domain") or []) & set(tgt.get("_problem_domain") or []))
                label = " · ".join(tax_overlaps[:2])
        edges.append({"source": src["id"], "target": tgt["id"], "weight": score, "label": label})
    return edges


async def _structurize_node(item: dict, provider: str) -> dict:
    """LLM으로 문서 1개를 구조화 JSON으로 변환."""
    from backend import llm as _llm
    content = item.get("text") or item.get("abstract") or ""
    title = item.get("title", "")

    prompt = f"""Analyze this document and extract structured metadata.

Title: {title}
Content: {content}

Return a JSON object with exactly these fields:
- summary: core content summary (under 500 chars)
- domain_type: exactly ONE of [tech, research, consumer, business, healthcare, general]
- tech_area: 1-2 items from [AI/ML, cloud, security, data, mobile, web, hardware, other]
- market: 1-2 items from [B2B, B2C, enterprise, developer, consumer, academic]
- problem_domain: 1-2 items from [automation, analytics, communication, productivity, infrastructure, security, UX, compliance]
- keywords: 5-10 specific technical terms (free form)
- entities: product/company/technology proper nouns (free form)"""

    try:
        resp = await _llm.complete(
            messages=[{"role": "user", "content": prompt}],
            tier="low",
            provider=provider,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.content)
    except Exception as exc:
        logger.warning("_structurize_node failed for %s: %s", title, exc)
        data = {}
    data = _normalize_structured_payload(data, content)

    return {
        "id": item["id"],
        "title": title,
        "source": item.get("source", ""),
        "url": item.get("url", ""),
        "abstract": data["summary"],
        "_domain_type": data["domain_type"],
        "_tech_area": data["tech_area"],
        "_market": data["market"],
        "_problem_domain": data["problem_domain"],
        "_keywords": data["keywords"],
        "_entities": data["entities"],
    }


async def _enrich_context_nodes(
    raw_items: list[dict],
    provider: str,
    on_node_done: "Callable[[dict, list[dict]], None] | None" = None,
) -> list[dict]:
    """문서 목록을 병렬로 구조화한다. 각 완료 시 on_node_done 콜백 호출."""
    sem = asyncio.Semaphore(10)
    enriched: list[dict] = []
    lock = asyncio.Lock()

    async def _limited(item):
        async with sem:
            node = await _structurize_node(item, provider)
        async with lock:
            existing = list(enriched)  # 현재까지 완료된 노드 목록 복사
            enriched.append(node)
        if on_node_done is not None:
            on_node_done(node, existing)
        return node

    return await asyncio.gather(*[_limited(item) for item in raw_items])


def _rank_nodes_by_relevance(nodes: list[dict], idea_text: str) -> list[dict]:
    """Sort nodes by relevance to idea_text. Uses structured fields if available, else keyword overlap."""
    idea_keywords = _extract_keywords(idea_text)
    if not idea_keywords:
        return nodes

    def score(node):
        # 구조화 필드가 있으면 우선 사용
        structured = _normalized_token_set(node.get("_keywords")) | _normalized_token_set(node.get("_entities"))
        if structured:
            return len(idea_keywords & structured)
        # fallback: regex
        return len(idea_keywords & _extract_keywords(f"{node.get('title', '')} {node.get('abstract', '')}"))

    return sorted(nodes, key=score, reverse=True)


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
        r.xadd(stream_key, {"data": json.dumps(event, ensure_ascii=False)}, maxlen=STREAM_MAXLEN)

    async def _run() -> None:
        from backend.analyzer import analyze
        from backend.context_builder import detect_domain
        from backend.reporter import generate_analysis_report, generate_final_report
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
        final_report_md: str = ""

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

            # Check for existing checkpoint (resume scenario)
            existing_checkpoint = await asyncio.to_thread(get_checkpoint, DB_PATH, sim_id)

            if existing_checkpoint:
                # Resume: restore pre-simulation data from checkpoint
                raw_items = existing_checkpoint["raw_items"]
                domain_str = existing_checkpoint["domain"]
                analysis_md = existing_checkpoint["analysis_md"]
                context_nodes = existing_checkpoint["context_nodes"]
                # 복원된 노드들을 순서대로 emit (LLM 재호출 없이)
                _restored_so_far: list[dict] = []
                for _node in context_nodes:
                    publish({
                        "type": "sim_graph_node",
                        "node": {
                            "id": _node["id"],
                            "title": _node.get("title", ""),
                            "source": _node.get("source", ""),
                            "url": _node.get("url", ""),
                        },
                    })
                    _new_edges = _calc_edges_for_node(_node, _restored_so_far)
                    if _new_edges:
                        publish({"type": "sim_graph_edges", "edges": _new_edges})
                    _restored_so_far.append(_node)
                # NOTE: do NOT publish sim_resume here — social_runner.py yields it
                # and tasks.py will forward it to Redis via the normal event loop below
            else:
                # Fresh run: run analysis pipeline
                publish({"type": "sim_progress", "message": "Searching external sources..."})

                # 소스 발견과 동시에 LLM 구조화를 병렬 실행 → 그래프 실시간 생성
                _structurize_sem = asyncio.Semaphore(5)
                _enriched_nodes: list[dict] = []
                _enriched_lock = asyncio.Lock()
                _structurize_tasks: list[asyncio.Task] = []
                _event_loop = asyncio.get_event_loop()

                async def _structurize_and_emit(item: dict) -> dict:
                    async with _structurize_sem:
                        node = await _structurize_node(item, provider)
                    async with _enriched_lock:
                        existing = list(_enriched_nodes)
                        _enriched_nodes.append(node)
                    publish({
                        "type": "sim_graph_node",
                        "node": {
                            "id": node["id"],
                            "title": node.get("title", ""),
                            "source": node.get("source", ""),
                            "url": node.get("url", ""),
                        },
                    })
                    new_edges = _calc_edges_for_node(node, existing)
                    if new_edges:
                        publish({"type": "sim_graph_edges", "edges": new_edges})
                    return node

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
                        # 발견 즉시 LLM 구조화 태스크 생성 → 그래프 실시간 업데이트
                        task = _event_loop.create_task(_structurize_and_emit(item))
                        _structurize_tasks.append(task)

                raw_items = await analyze(
                    config["input_text"],
                    limits=config.get("source_limits") or None,
                    on_source_done=on_source_done,
                    provider=provider,
                )
                await checkpoint()

                # 진행 중인 구조화 태스크 모두 완료 대기
                if _structurize_tasks:
                    _results = await asyncio.gather(*_structurize_tasks, return_exceptions=True)
                    context_nodes = [n for n in _results if isinstance(n, dict)]
                else:
                    context_nodes = [{
                        "id": "input",
                        "title": config["input_text"][:80],
                        "source": "input_text",
                        "abstract": config["input_text"][:300],
                    }]

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

            context_nodes = _rank_nodes_by_relevance(context_nodes, config["input_text"])
            edges = _build_structured_edges(context_nodes)

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
                edges=edges,
                provider=provider,
                checkpoint=existing_checkpoint,
            ):
                await checkpoint()
                if event["type"] == "sim_checkpoint_data":
                    # Enrich with analysis_md and raw_items (not available in social_runner)
                    await asyncio.to_thread(
                        save_checkpoint,
                        DB_PATH,
                        sim_id,
                        event["round_num"],
                        event["platform_states"],
                        event["personas"],
                        event["context_nodes"],
                        event["domain"] or domain_str,
                        analysis_md,
                        raw_items,
                    )
                    continue  # do NOT publish to Redis
                if event["type"] == "sim_report":
                    data = event["data"]
                    posts_by_platform = data.get("platform_states", {})
                    personas_by_platform = data.get("personas", {})
                    report_json = data.get("report_json", {})
                    report_md = data.get("markdown", "")
                publish(event)

            await checkpoint()
            publish({"type": "sim_progress", "message": "Generating final report..."})
            try:
                final_report_md = await generate_final_report(
                    analysis_md=analysis_md,
                    report_json=report_json,
                    input_text=config["input_text"],
                    language=config["language"],
                    provider=provider,
                )
                publish({"type": "sim_final_report", "data": {"markdown": final_report_md}})
            except Exception as _e:
                logger.warning("Final report generation failed: %s", _e)
                final_report_md = "## Final Report\n\n_Generation failed._"
            save_sim_results(
                DB_PATH,
                sim_id,
                posts_by_platform,
                personas_by_platform,
                report_json,
                report_md,
                analysis_md=analysis_md,
                raw_items=raw_items,
                final_report_md=final_report_md,
                context_nodes=context_nodes,
            )
            completed = await asyncio.to_thread(
                update_simulation_status,
                DB_PATH,
                sim_id,
                "completed",
                allowed_current_statuses={"running"},
                require_not_cancelled=True,
            )
            if completed:
                await asyncio.to_thread(delete_checkpoint, DB_PATH, sim_id)
            else:
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
