from __future__ import annotations
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", str(Path(__file__).parent.parent / "noosphere.db")))

ACTIVE_SIMULATION_STATUS = "running"
TERMINAL_SIMULATION_STATUSES = {"completed", "failed", "partial"}
logger = logging.getLogger(__name__)


def _conn(path: str | Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_columns(
    conn: sqlite3.Connection,
    table_name: str,
    column_defs: dict[str, str],
) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_def in column_defs.items():
        if column_name in existing_columns:
            continue
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"
        )


def _drop_column_if_exists(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in existing_columns:
        conn.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")


def init_db(path: str | Path = DB_PATH) -> None:
    with _conn(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                input_text TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'English',
                config_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'running',
                domain TEXT NOT NULL DEFAULT '',
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                heartbeat_at TEXT,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sim_results (
                sim_id TEXT PRIMARY KEY,
                posts_json TEXT NOT NULL DEFAULT '{}',
                personas_json TEXT NOT NULL DEFAULT '{}',
                report_json TEXT NOT NULL DEFAULT '{}',
                report_md TEXT NOT NULL DEFAULT '',
                analysis_md TEXT NOT NULL DEFAULT '',
                sources_json TEXT NOT NULL DEFAULT '[]',
                final_report_md TEXT NOT NULL DEFAULT '',
                context_nodes_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS sim_checkpoints (
                sim_id TEXT PRIMARY KEY,
                last_round INTEGER NOT NULL,
                platform_states_json TEXT NOT NULL,
                personas_json TEXT NOT NULL,
                context_nodes_json TEXT NOT NULL,
                domain TEXT NOT NULL,
                analysis_md TEXT NOT NULL,
                raw_items_json TEXT NOT NULL,
                saved_at TEXT NOT NULL
            );
        """)
        _ensure_columns(conn, "sim_results", {
            "analysis_md": "TEXT NOT NULL DEFAULT ''",
            "sources_json": "TEXT NOT NULL DEFAULT '[]'",
            "final_report_md": "TEXT NOT NULL DEFAULT ''",
            "context_nodes_json": "TEXT NOT NULL DEFAULT '[]'",
            "gtm_md": "TEXT NOT NULL DEFAULT ''",
        })
        _ensure_columns(conn, "simulations", {
            "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
            "started_at": "TEXT",
            "heartbeat_at": "TEXT",
            "finished_at": "TEXT",
        })
        _ensure_columns(conn, "sim_checkpoints", {
            "analysis_md": "TEXT NOT NULL DEFAULT ''",
            "raw_items_json": "TEXT NOT NULL DEFAULT '[]'",
            "saved_at": "TEXT NOT NULL DEFAULT ''",
            "runner_state_json": "TEXT NOT NULL DEFAULT '{}'",
        })
        _drop_column_if_exists(conn, "sim_checkpoints", "ontology_json")
        conn.commit()


def create_simulation(
    path: str | Path,
    sim_id: str,
    input_text: str,
    language: str,
    config: dict,
    domain: str,
) -> None:
    now = _utc_now_iso()
    with _conn(path) as conn:
        conn.execute(
            """
            INSERT INTO simulations (
                id, created_at, input_text, language, config_json, status, domain,
                cancel_requested, started_at, heartbeat_at, finished_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                sim_id,
                now,
                input_text,
                language,
                json.dumps(config, ensure_ascii=False),
                ACTIVE_SIMULATION_STATUS,
                domain,
                0,
                None,
                None,
                None,
            ),
        )


def update_simulation_status(
    path: str | Path,
    sim_id: str,
    status: str,
    *,
    allowed_current_statuses: set[str] | None = None,
    require_not_cancelled: bool = False,
) -> bool:
    now = _utc_now_iso()
    clauses = ["id=?"]
    where_params: list[object] = [sim_id]
    set_params: list[object] = [status]

    if status in TERMINAL_SIMULATION_STATUSES:
        set_clause = "status=?, finished_at=?"
        set_params.append(now)
    else:
        # running 상태로 전환 시 finished_at을 초기화 (재개 시나리오)
        set_clause = "status=?, finished_at=NULL"

    if allowed_current_statuses:
        placeholders = ",".join("?" for _ in allowed_current_statuses)
        clauses.append(f"status IN ({placeholders})")
        where_params.extend(sorted(allowed_current_statuses))
    if require_not_cancelled:
        clauses.append("cancel_requested=0")

    with _conn(path) as conn:
        cur = conn.execute(
            f"UPDATE simulations SET {set_clause} WHERE {' AND '.join(clauses)}",
            [*set_params, *where_params],
        )
    return cur.rowcount > 0


def update_simulation_domain(path: str | Path, sim_id: str, domain: str) -> None:
    with _conn(path) as conn:
        conn.execute(
            "UPDATE simulations SET domain=? WHERE id=?",
            (domain, sim_id),
        )


def request_simulation_cancel(path: str | Path, sim_id: str) -> bool:
    now = _utc_now_iso()
    with _conn(path) as conn:
        cur = conn.execute(
            """
            UPDATE simulations
            SET cancel_requested=1, status='failed', finished_at=?
            WHERE id=? AND status=?
            """,
            (now, sim_id, ACTIVE_SIMULATION_STATUS),
        )
    return cur.rowcount > 0


def mark_simulation_started(path: str | Path, sim_id: str) -> bool:
    now = _utc_now_iso()
    with _conn(path) as conn:
        cur = conn.execute(
            """
            UPDATE simulations
            SET started_at=?, heartbeat_at=?, finished_at=NULL
            WHERE id=? AND status=? AND cancel_requested=0
            """,
            (now, now, sim_id, ACTIVE_SIMULATION_STATUS),
        )
    return cur.rowcount > 0


def touch_simulation_heartbeat(path: str | Path, sim_id: str) -> bool:
    now = _utc_now_iso()
    with _conn(path) as conn:
        cur = conn.execute(
            """
            UPDATE simulations
            SET heartbeat_at=?
            WHERE id=? AND status=? AND cancel_requested=0
            """,
            (now, sim_id, ACTIVE_SIMULATION_STATUS),
        )
    return cur.rowcount > 0


def simulation_cancel_requested(path: str | Path, sim_id: str) -> bool:
    with _conn(path) as conn:
        row = conn.execute(
            "SELECT status, cancel_requested FROM simulations WHERE id=?",
            (sim_id,),
        ).fetchone()
    if row is None:
        return True
    return row["status"] != ACTIVE_SIMULATION_STATUS or bool(row["cancel_requested"])


def _stale_conditions(now_iso: str, queue_timeout_seconds: int, heartbeat_timeout_seconds: int) -> tuple[str, list[object]]:
    return (
        """
        (
            (started_at IS NULL AND datetime(created_at) <= datetime(?, ?))
            OR
            (started_at IS NOT NULL AND (
                heartbeat_at IS NULL
                OR datetime(heartbeat_at) <= datetime(?, ?)
            ))
        )
        """,
        [
            now_iso,
            f"-{queue_timeout_seconds} seconds",
            now_iso,
            f"-{heartbeat_timeout_seconds} seconds",
        ],
    )


def reconcile_stale_simulations(
    path: str | Path,
    *,
    queue_timeout_seconds: int,
    heartbeat_timeout_seconds: int,
) -> int:
    now = _utc_now_iso()
    stale_conditions, params = _stale_conditions(now, queue_timeout_seconds, heartbeat_timeout_seconds)
    with _conn(path) as conn:
        cur = conn.execute(
            f"""
            UPDATE simulations
            SET status='failed', finished_at=?
            WHERE status=? AND {stale_conditions}
            """,
            [now, ACTIVE_SIMULATION_STATUS, *params],
        )
    return cur.rowcount


def count_active_simulations(
    path: str | Path,
    *,
    queue_timeout_seconds: int,
    heartbeat_timeout_seconds: int,
) -> int:
    now = _utc_now_iso()
    stale_conditions, params = _stale_conditions(now, queue_timeout_seconds, heartbeat_timeout_seconds)
    with _conn(path) as conn:
        (count,) = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM simulations
            WHERE status=?
            AND NOT {stale_conditions}
            """,
            [ACTIVE_SIMULATION_STATUS, *params],
        ).fetchone()
    return int(count)


def get_simulation(path: str | Path, sim_id: str) -> dict | None:
    with _conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM simulations WHERE id=?", (sim_id,)
        ).fetchone()
    return dict(row) if row else None


def save_sim_results(
    path: str | Path,
    sim_id: str,
    posts: dict,
    personas: dict,
    report_json: dict,
    report_md: str,
    analysis_md: str = "",
    raw_items: list[dict] | None = None,
    final_report_md: str = "",
    context_nodes: list[dict] | None = None,
    gtm_md: str = "",
) -> None:
    with _conn(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sim_results "
            "(sim_id, posts_json, personas_json, report_json, report_md, analysis_md, sources_json, final_report_md, context_nodes_json, gtm_md) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sim_id, json.dumps(posts, ensure_ascii=False), json.dumps(personas, ensure_ascii=False),
             json.dumps(report_json, ensure_ascii=False), report_md, analysis_md,
             json.dumps(raw_items or [], ensure_ascii=False), final_report_md,
             json.dumps(context_nodes or [], ensure_ascii=False), gtm_md),
        )


def get_sim_results(path: str | Path, sim_id: str) -> dict | None:
    with _conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM sim_results WHERE sim_id=?", (sim_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["posts_json"] = json.loads(d.get("posts_json") or "{}")
    d["personas_json"] = json.loads(d.get("personas_json") or "{}")
    d["report_json"] = json.loads(d.get("report_json") or "null")
    d["sources_json"] = json.loads(d.get("sources_json") or "[]")
    d["context_nodes_json"] = json.loads(d.get("context_nodes_json") or "[]")
    d["gtm_md"] = d.get("gtm_md") or ""
    return d


def save_checkpoint(
    path: str | Path,
    sim_id: str,
    last_round: int,
    platform_states: dict,
    personas: dict,
    context_nodes: list,
    domain: str,
    analysis_md: str,
    raw_items: list,
    runner_state: dict | None = None,
) -> None:
    now = _utc_now_iso()
    with _conn(path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sim_checkpoints
            (sim_id, last_round, platform_states_json, personas_json, context_nodes_json,
             domain, analysis_md, raw_items_json, saved_at, runner_state_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                sim_id,
                last_round,
                json.dumps(platform_states, ensure_ascii=False),
                json.dumps(personas, ensure_ascii=False),
                json.dumps(context_nodes, ensure_ascii=False),
                domain,
                analysis_md,
                json.dumps(raw_items, ensure_ascii=False),
                now,
                json.dumps(runner_state or {}, ensure_ascii=False),
            ),
        )


def get_checkpoint(path: str | Path, sim_id: str) -> dict | None:
    with _conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM sim_checkpoints WHERE sim_id=?", (sim_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["platform_states"] = json.loads(d.pop("platform_states_json"))
        d["personas"] = json.loads(d.pop("personas_json"))
        d["context_nodes"] = json.loads(d.pop("context_nodes_json"))
        d["raw_items"] = json.loads(d.pop("raw_items_json"))
        d["runner_state"] = json.loads(d.pop("runner_state_json", "{}") or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        logger.warning("Checkpoint %s is corrupted and will be ignored: %s", sim_id, exc)
        return None
    d.pop("ontology_json", None)
    return d


def delete_checkpoint(path: str | Path, sim_id: str) -> None:
    with _conn(path) as conn:
        conn.execute("DELETE FROM sim_checkpoints WHERE sim_id=?", (sim_id,))


def list_history(path: str | Path = DB_PATH, limit: int = 50) -> list[dict]:
    with _conn(path) as conn:
        rows = conn.execute(
            """SELECT s.id, s.created_at, s.input_text, s.language, s.config_json,
                      s.status, s.domain, s.started_at, s.finished_at,
                      r.report_json AS _report_json
               FROM simulations s
               LEFT JOIN sim_results r ON s.id = r.sim_id
               ORDER BY s.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["input_text_snippet"] = d["input_text"][:60]
        config = json.loads(d.pop("config_json")) if d.get("config_json") else {}
        d["config"] = config
        d["max_agents"] = config.get("max_agents")
        d["num_rounds"] = config.get("num_rounds")

        # duration_seconds: finished_at - started_at (Python 계산)
        started_at = d.pop("started_at", None)
        finished_at = d.pop("finished_at", None)
        duration_seconds = None
        if started_at and finished_at:
            try:
                dt_start = datetime.fromisoformat(started_at)
                dt_end = datetime.fromisoformat(finished_at)
                duration_seconds = int((dt_end - dt_start).total_seconds())
                if duration_seconds < 0:
                    duration_seconds = None
            except (ValueError, TypeError):
                pass
        d["duration_seconds"] = duration_seconds

        # Extract verdict, evidence_count, adoption_score from report_json if available
        raw_report = d.pop("_report_json", None)
        verdict = None
        evidence_count = None
        adoption_score = None
        if raw_report:
            try:
                report = json.loads(raw_report)
                if isinstance(report, dict):
                    verdict = report.get("verdict")
                    evidence_count = report.get("evidence_count")
                    adoption_score = report.get("adoption_score")
            except (TypeError, json.JSONDecodeError):
                pass
        d["verdict"] = verdict
        d["evidence_count"] = evidence_count
        d["adoption_score"] = adoption_score

        result.append(d)
    return result


def delete_simulation(path: str | Path, sim_id: str) -> bool:
    """3개 테이블에서 시뮬레이션 데이터를 완전 삭제. 삭제된 행이 있으면 True 반환."""
    with _conn(path) as conn:
        cur = conn.execute("DELETE FROM simulations WHERE id=?", (sim_id,))
        conn.execute("DELETE FROM sim_results WHERE sim_id=?", (sim_id,))
        conn.execute("DELETE FROM sim_checkpoints WHERE sim_id=?", (sim_id,))
    return cur.rowcount > 0
