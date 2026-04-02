from __future__ import annotations
import asyncio
import contextlib
import json
import logging
import os
import signal
import time
from collections.abc import Callable

import redis as _redis_sync

from backend.celery_app import celery_app, REDIS_URL
from backend.db import (
    save_sim_results,
    update_simulation_status,
    update_simulation_domain,
    DB_PATH,
    mark_simulation_started,
    touch_simulation_heartbeat,
    simulation_cancel_requested,
    save_checkpoint,
    get_checkpoint,
    delete_checkpoint,
)
from backend.simulation.taxonomy import (
    DOMAIN_TYPES as _DOMAIN_TYPES,
    TECH_AREAS as _TECH_AREAS,
    MARKETS as _MARKETS,
    PROBLEM_DOMAINS as _PROBLEM_DOMAINS,
    coerce_enum as _coerce_enum,
    coerce_string_list as _coerce_string_list,
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

# entities에서 제거할 플랫폼/소스 이름 (노드 간 의미없는 연결 방지)
_ENTITY_BLOCKLIST = {
    "reddit", "hackernews", "hacker news", "github", "producthunt", "product hunt",
    "indiehackers", "indie hackers", "linkedin", "twitter", "youtube",
    "google", "apple", "amazon", "microsoft",
}


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


def _build_structured_edges(nodes: list[dict], min_score: int = 8) -> list[dict]:
    """구조화 필드 기반 가중 엣지 빌딩."""
    edges: list[dict] = []
    node_list = [n for n in nodes if n.get("id")]

    # 이중 루프 진입 전에 모든 노드의 필드를 미리 계산하여 dict에 저장
    _cache_entities: dict[str, set[str]] = {}
    _cache_keywords: dict[str, set[str]] = {}
    _cache_domain: dict[str, str | None] = {}
    _cache_tech_area: dict[str, set[str]] = {}
    _cache_market: dict[str, set[str]] = {}
    _cache_problem_domain: dict[str, set[str]] = {}
    for n in node_list:
        nid = n["id"]
        _cache_entities[nid] = _normalized_token_set(n.get("_entities"))
        _cache_keywords[nid] = _normalized_token_set(n.get("_keywords"))
        _cache_domain[nid] = _coerce_enum(n.get("_domain_type"), _DOMAIN_TYPES)
        _cache_tech_area[nid] = set(_coerce_string_list(n.get("_tech_area"), allowed=_TECH_AREAS))
        _cache_market[nid] = set(_coerce_string_list(n.get("_market"), allowed=_MARKETS))
        _cache_problem_domain[nid] = set(_coerce_string_list(n.get("_problem_domain"), allowed=_PROBLEM_DOMAINS))

    for i, src in enumerate(node_list):
        sid = src["id"]
        src_entities = _cache_entities[sid]
        src_kw = _cache_keywords[sid]
        src_domain = _cache_domain[sid]
        src_tech = _cache_tech_area[sid]
        src_market = _cache_market[sid]
        src_prob = _cache_problem_domain[sid]
        for tgt in node_list[i + 1:]:
            tid = tgt["id"]
            tgt_entities = _cache_entities[tid]
            tgt_kw = _cache_keywords[tid]
            score = 0
            # entities × 3
            score += len(src_entities & tgt_entities) * 3
            # keywords × 2
            score += len(src_kw & tgt_kw) * 2
            # domain_type × 1
            tgt_domain = _cache_domain[tid]
            if src_domain and src_domain == tgt_domain:
                score += 1
            # tech_area × 1
            score += len(src_tech & _cache_tech_area[tid])
            # market × 1
            score += len(src_market & _cache_market[tid])
            # problem_domain × 1
            score += len(src_prob & _cache_problem_domain[tid])

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
                        if src_domain and src_domain == tgt_domain:
                            tax_overlaps.append(src_domain)
                        tax_overlaps += list(src_tech & _cache_tech_area[tid])
                        tax_overlaps += list(src_market & _cache_market[tid])
                        tax_overlaps += list(src_prob & _cache_problem_domain[tid])
                        label = " · ".join(tax_overlaps[:2])
                edges.append({"source": sid, "target": tid, "weight": score, "label": label})
    return edges


def _top_k_edges(edges: list[dict], k: int = 3) -> list[dict]:
    """노드당 엣지 선별.
    - 최고 점수 그룹은 전부 포함 (k 초과 허용)
    - 이후 그룹은 남은 슬롯(k - 최고그룹수)을 채울 때까지 추가
    - 양쪽 노드 중 어느 한쪽이라도 거부하면 제거
    예) 10점×5, 9점×10 → 10점 5개 전부 (9점은 A 노드가 거부)
        10점×1, 9점×1, 8점×2 → 10점 1개 + 9점 1개 + 8점 1개 = 3개
    """
    from collections import defaultdict
    from itertools import groupby

    node_edges: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        node_edges[e["source"]].append(e)
        node_edges[e["target"]].append(e)

    rejected: set[int] = set()
    for node_edge_list in node_edges.values():
        sorted_edges = sorted(node_edge_list, key=lambda x: x["weight"], reverse=True)
        remaining = k
        first = True
        for _, group in groupby(sorted_edges, key=lambda x: x["weight"]):
            group_list = list(group)
            if first:
                remaining = max(0, k - len(group_list))
                first = False
            else:
                if remaining <= 0 or len(group_list) > remaining:
                    # 슬롯 부족 시 그룹 전체 버림 (반만 추가하지 않음)
                    for e in group_list:
                        rejected.add(id(e))
                else:
                    remaining -= len(group_list)

    return [e for e in edges if id(e) not in rejected]


def _calc_edges_for_node(new_node: dict, existing_nodes: list[dict], min_score: int = 8) -> list[dict]:
    """새 노드 1개와 기존 노드 목록 간의 엣지만 계산한다."""
    if not new_node.get("id"):
        return []
    edges: list[dict] = []
    src = new_node
    src_entities = _normalized_token_set(src.get("_entities"))
    src_kw = _normalized_token_set(src.get("_keywords"))
    for tgt in existing_nodes:
        if not tgt.get("id"):
            continue
        score = 0
        tgt_entities = _normalized_token_set(tgt.get("_entities"))
        tgt_kw = _normalized_token_set(tgt.get("_keywords"))
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


async def _summarize_idea_node(input_text: str) -> dict:
    """사용자 아이디어를 1000자 이내로 요약하고 구조화된 그래프 노드로 변환."""
    from backend import llm as _llm

    prompt = f"""Analyze this product idea and extract structured metadata.

Product idea:
{input_text[:4000]}

Return a JSON object with exactly these fields:
- summary: concise product summary under 1000 characters (clean prose, remove excess whitespace and special characters)
- title: product name or core value proposition (under 80 chars)
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
            max_tokens=768,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.content)
    except Exception as exc:
        logger.warning("_summarize_idea_node failed: %s", exc)
        data = {}

    raw_title = data.get("title") if isinstance(data.get("title"), str) else ""
    if not raw_title.strip():
        raw_title = next((line.strip() for line in input_text.splitlines() if line.strip()), input_text)
    title = raw_title.strip()[:80]

    data = _normalize_structured_payload(data, input_text[:1000])
    return {
        "id": "idea",
        "title": title,
        "source": "idea",
        "url": "",
        "abstract": data["summary"],
        "_domain_type": data["domain_type"],
        "_tech_area": data["tech_area"],
        "_market": data["market"],
        "_problem_domain": data["problem_domain"],
        "_keywords": data["keywords"],
        "_entities": data["entities"],
    }


async def _structurize_node(item: dict) -> dict:
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
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.content)
    except Exception as exc:
        logger.warning("_structurize_node failed for %s: %s", title, exc)
        data = {}
    data = _normalize_structured_payload(data, content)

    filtered_entities = [
        e for e in data["entities"]
        if e.lower() not in _ENTITY_BLOCKLIST
    ]
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
        "_entities": filtered_entities,
    }


async def _enrich_context_nodes(
    raw_items: list[dict],
    on_node_done: "Callable[[dict, list[dict]], None] | None" = None,
) -> list[dict]:
    """문서 목록을 병렬로 구조화한다. 각 완료 시 on_node_done 콜백 호출."""
    sem = asyncio.Semaphore(10)
    enriched: list[dict] = []
    lock = asyncio.Lock()

    async def _limited(item):
        async with sem:
            node = await _structurize_node(item)
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
        raw_items: list = []
        context_nodes: list = []
        posts_by_platform: dict = {}
        personas_by_platform: dict = {}
        report_json: dict = {}
        report_md: str = ""
        final_report_md: str = ""
        gtm_md: str = ""
        domain_str: str = ""
        _sim_done_published = False

        try:
            if not await asyncio.to_thread(mark_simulation_started, DB_PATH, sim_id):
                logger.info("Simulation %s will not start because it is no longer active", sim_id)
                return

            provider = "openai"
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
                    _new_edges = _top_k_edges(_calc_edges_for_node(_node, _restored_so_far))
                    if _new_edges:
                        publish({"type": "sim_graph_edges", "edges": _new_edges})
                    _restored_so_far.append(_node)
                # NOTE: do NOT publish sim_resume here — social_runner.py yields it
                # and tasks.py will forward it to Redis via the normal event loop below
            else:
                # Fresh run: run analysis pipeline
                publish({"type": "sim_progress", "message": "Analyzing your idea..."})
                idea_node = await _summarize_idea_node(config["input_text"])
                publish({
                    "type": "sim_graph_node",
                    "node": {
                        "id": idea_node["id"],
                        "title": idea_node.get("title", ""),
                        "source": idea_node.get("source", ""),
                        "url": idea_node.get("url", ""),
                    },
                })

                publish({"type": "sim_progress", "message": "Searching external sources..."})

                # 소스 발견과 동시에 LLM 구조화를 병렬 실행 → 그래프 실시간 생성
                _structurize_sem = asyncio.Semaphore(5)
                _enriched_nodes: list[dict] = [idea_node]  # 아이디어 노드로 초기화 → 외부 소스들이 자동으로 엣지 연결
                _enriched_lock = asyncio.Lock()
                _structurize_tasks: list[asyncio.Task] = []
                _event_loop = asyncio.get_running_loop()

                async def _structurize_and_emit(item: dict) -> dict:
                    async with _structurize_sem:
                        node = await _structurize_node(item)
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
                    new_edges = _top_k_edges(_calc_edges_for_node(node, existing))
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
                )
                await checkpoint()

                # 진행 중인 구조화 태스크 모두 완료 대기
                if _structurize_tasks:
                    _results = await asyncio.gather(*_structurize_tasks, return_exceptions=True)
                    context_nodes = [idea_node] + [n for n in _results if isinstance(n, dict)]
                else:
                    context_nodes = [idea_node]

                domain_str = await detect_domain(config["input_text"])
                await asyncio.to_thread(update_simulation_domain, DB_PATH, sim_id, domain_str)

                publish({
                    "type": "sim_progress",
                    "message": f"Domain: {domain_str}. Generating analysis report...",
                })
                # Select top-3 competitor nodes by relevance to the idea
                _competitor_candidates = [n for n in context_nodes if n.get("id") != "idea"]
                _ranked_competitors = _rank_nodes_by_relevance(_competitor_candidates, config["input_text"])
                _top_competitors = _ranked_competitors[:3]

                analysis_md = await generate_analysis_report(
                    raw_items=raw_items,
                    domain=domain_str,
                    input_text=idea_node["abstract"],
                    language=config["language"],
                    idea_title=idea_node["title"],
                    top_competitors=_top_competitors,
                )
                await checkpoint()
                publish({"type": "sim_analysis", "data": {"markdown": analysis_md}})

            context_nodes = _rank_nodes_by_relevance(context_nodes, config["input_text"])
            edges = _top_k_edges(_build_structured_edges(context_nodes))

            _idea_node = next((n for n in context_nodes if n.get("id") == "idea"), None)
            idea_summary = _idea_node["abstract"] if _idea_node else config["input_text"]

            publish({
                "type": "sim_progress",
                "message": f"Starting simulation with {len(context_nodes)} context nodes...",
            })

            sim_start_time = time.time()
            rounds_start_time: float | None = None
            async for event in run_simulation(
                input_text=idea_summary,
                seed_text=config["input_text"],
                context_nodes=context_nodes,
                domain=domain_str,
                max_agents=config["max_agents"],
                num_rounds=config["num_rounds"],
                platforms=config["platforms"],
                language=config["language"],
                activation_rate=config["activation_rate"],
                edges=edges,
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
                        event.get("runner_state"),
                    )
                    continue  # do NOT publish to Redis
                if event["type"] == "sim_done":
                    continue  # defer sim_done until after DB save
                if event["type"] == "sim_report":
                    data = event["data"]
                    posts_by_platform = data.get("platform_states", {})
                    personas_by_platform = data.get("personas", {})
                    report_json = data.get("report_json", {})
                    report_md = data.get("markdown", "")
                publish(event)
                # Emit ETA after each round summary
                if event.get("type") == "sim_round_summary":
                    total_rounds = config["num_rounds"]
                    elapsed_sec = time.time() - sim_start_time
                    completed_rounds = event.get("round_num", 1)
                    remaining_rounds = total_rounds - completed_rounds
                    # Record timestamp after round 1 completes so persona
                    # generation time is excluded from the per-round average.
                    if completed_rounds == 1:
                        rounds_start_time = time.time()
                    if completed_rounds > 0:
                        if completed_rounds >= 2 and rounds_start_time:
                            avg_sec_per_round = (time.time() - rounds_start_time) / (completed_rounds - 1)
                        else:
                            avg_sec_per_round = elapsed_sec / completed_rounds
                        eta_sec = avg_sec_per_round * remaining_rounds
                        publish({
                            "type": "sim_eta",
                            "eta_seconds": round(eta_sec),
                            "elapsed_seconds": round(elapsed_sec),
                            "completed_rounds": completed_rounds,
                            "total_rounds": total_rounds,
                        })

            await checkpoint()
            publish({"type": "sim_progress", "message": "Generating launch strategy..."})
            try:
                from backend.reporter import generate_gtm_report
                # Extract top posts per platform for GTM report context
                top_posts_for_gtm: list[dict] = []
                for _platform_name, _platform_posts in posts_by_platform.items():
                    if not isinstance(_platform_posts, list):
                        continue
                    _non_seed = [p for p in _platform_posts if isinstance(p, dict) and not str(p.get("id", "")).startswith("__seed__")]
                    _top_3 = sorted(_non_seed, key=lambda p: p.get("upvotes", 0) - p.get("downvotes", 0), reverse=True)[:3]
                    top_posts_for_gtm.extend(_top_3)
                # interaction_network에서 상위 5개 페어 요약
                interaction_summary = ""
                if report_json and report_json.get("interaction_network"):
                    pairs = sorted(
                        report_json["interaction_network"],
                        key=lambda x: x.get("count", 0),
                        reverse=True
                    )[:5]
                    lines = []
                    for p in pairs:
                        fs = p.get("from_segment", p.get("from_name", "?"))
                        ts = p.get("to_segment", p.get("to_name", "?"))
                        pattern = p.get("sentiment_pattern", "mixed")
                        lines.append(f"- {fs} -> {ts}: {pattern} ({p.get('count', 0)} exchanges)")
                    interaction_summary = "Segment interaction patterns:\n" + "\n".join(lines)

                # debate_timeline에서 turning_points 있는 상위 3개 추출
                debate_tl = (report_json or {}).get("debate_timeline") or []
                dh_lines: list[str] = []
                debates_with_tp = [d for d in debate_tl if d.get("turning_points")]
                debates_with_tp.sort(
                    key=lambda d: abs(d["turning_points"][0].get("delta_pct") or 0),
                    reverse=True,
                )
                for debate in debates_with_tp[:3]:
                    tps = debate.get("turning_points") or []
                    tp = tps[0]  # 가장 큰 turning point
                    snippet = debate.get("root_content_snippet", "")[:60]
                    direction = tp.get("direction", "")
                    round_n = tp.get("round", "?")
                    delta = tp.get("delta_pct") or 0
                    trigger = tp.get("trigger_snippet", "")[:50]
                    dh_lines.append(
                        f"- \"{snippet}\" \u2192 R{round_n} {direction} shift ({delta:.0f}%) "
                        + (f"triggered by: \"{trigger}\"" if trigger else "")
                    )
                debate_highlights = "\n".join(dh_lines)

                gtm_md = await generate_gtm_report(
                    report_json=report_json,
                    analysis_md=analysis_md,
                    input_text=idea_summary,
                    language=config["language"],
                    platform_summaries=report_json.get("platform_summaries"),
                    top_posts=top_posts_for_gtm if top_posts_for_gtm else None,
                    interaction_summary=interaction_summary,
                    conversion_funnel=report_json.get("segment_conversion_funnel"),
                    unaddressed_concerns=report_json.get("unaddressed_concerns"),
                    debate_highlights=debate_highlights,
                )
                publish({"type": "sim_gtm_report", "data": {"markdown": gtm_md}})
            except Exception as _e:
                logger.warning("GTM report generation failed: %s", _e)
                gtm_md = "## Launch Strategy\n\n_Generation failed._"
            publish({"type": "sim_progress", "message": "Generating final report..."})
            try:
                # Build sentiment distribution from segments for confidence assessment
                _sentiment_dist: dict[str, int] = {}
                for _seg in report_json.get("segments", []):
                    _s = _seg.get("sentiment", "neutral")
                    _sentiment_dist[_s] = _sentiment_dist.get(_s, 0) + 1
                final_report_md = await generate_final_report(
                    analysis_md=analysis_md,
                    report_json=report_json,
                    input_text=idea_summary,
                    language=config["language"],
                    gtm_md=gtm_md,
                    agent_count=config["max_agents"],
                    round_count=config["num_rounds"],
                    sentiment_distribution=_sentiment_dist,
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
                gtm_md=gtm_md,
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
            # DB 저장 완료 후 sim_done 발행 → 프론트가 이 시점에 navigate
            publish({"type": "sim_done"})
            _sim_done_published = True
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
            _has_partial = posts_by_platform and any(posts_by_platform.values())
            if _has_partial:
                try:
                    save_sim_results(
                        DB_PATH,
                        sim_id,
                        posts_by_platform,
                        personas_by_platform,
                        report_json,
                        report_md,
                        analysis_md=analysis_md,
                        raw_items=raw_items,
                        context_nodes=context_nodes,
                        gtm_md=gtm_md,
                        final_report_md=final_report_md,
                    )
                    await asyncio.to_thread(
                        update_simulation_status,
                        DB_PATH,
                        sim_id,
                        "partial",
                        allowed_current_statuses={"running"},
                    )
                    logger.info("Simulation %s: partial results saved", sim_id)
                except Exception:
                    logger.warning("Simulation %s: failed to save partial results", sim_id, exc_info=True)
            publish({
                "type": "sim_error",
                "message": str(exc),
                "partial_saved": _has_partial,
            })
            if not _has_partial:
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
            if not _sim_done_published:
                publish({"type": "sim_done"})
            r.expire(stream_key, STREAM_TTL)

    try:
        asyncio.run(_run())
    finally:
        r.close()
