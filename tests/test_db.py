import pytest
import sqlite3
from datetime import datetime, timedelta, timezone

from backend.db import init_db, create_simulation, update_simulation_status, \
    save_sim_results, get_sim_results, list_history, get_simulation, \
    request_simulation_cancel, mark_simulation_started, touch_simulation_heartbeat, \
    count_active_simulations, reconcile_stale_simulations

@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path

def test_create_and_get_simulation(db_path):
    sim_id = "test-sim-id-001"
    create_simulation(db_path, sim_id, "My SaaS app", "English",
                      {"num_rounds": 5}, "saas")
    row = get_simulation(db_path, sim_id)
    assert row["input_text"] == "My SaaS app"
    assert row["status"] == "running"

def test_update_status(db_path):
    sim_id = "test-sim-id-002"
    create_simulation(db_path, sim_id, "test", "English", {}, "tech")
    update_simulation_status(db_path, sim_id, "completed")
    row = get_simulation(db_path, sim_id)
    assert row["status"] == "completed"

def test_save_and_get_results(db_path):
    sim_id = "test-sim-id-003"
    create_simulation(db_path, sim_id, "test", "English", {}, "tech")
    save_sim_results(db_path, sim_id,
                     posts={"hackernews": []},
                     personas={"hackernews": []},
                     report_json={"verdict": "positive"},
                     report_md="## Report")
    result = get_sim_results(db_path, sim_id)
    assert result["report_json"]["verdict"] == "positive"

def test_list_history(db_path):
    create_simulation(db_path, "id-a", "App one", "English", {}, "saas")
    create_simulation(db_path, "id-b", "App two", "Korean", {}, "fintech")
    rows = list_history(db_path)
    assert len(rows) == 2
    assert rows[0]["input_text_snippet"] is not None


def test_cancel_prevents_completion_overwrite(db_path):
    sim_id = "test-sim-id-004"
    create_simulation(db_path, sim_id, "test", "English", {}, "tech")

    assert request_simulation_cancel(db_path, sim_id) is True
    assert update_simulation_status(
        db_path,
        sim_id,
        "completed",
        allowed_current_statuses={"running"},
        require_not_cancelled=True,
    ) is False

    row = get_simulation(db_path, sim_id)
    assert row["status"] == "failed"
    assert row["cancel_requested"] == 1


def test_stale_running_jobs_are_excluded_and_reconciled(db_path):
    active_id = "active-sim"
    stale_id = "stale-sim"

    create_simulation(db_path, active_id, "active", "English", {}, "tech")
    create_simulation(db_path, stale_id, "stale", "English", {}, "tech")
    assert mark_simulation_started(db_path, active_id) is True
    assert mark_simulation_started(db_path, stale_id) is True
    assert touch_simulation_heartbeat(db_path, active_id) is True

    stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE simulations SET heartbeat_at=?, started_at=? WHERE id=?",
            (stale_ts, stale_ts, stale_id),
        )
        conn.commit()

    assert count_active_simulations(
        db_path,
        queue_timeout_seconds=60,
        heartbeat_timeout_seconds=60,
    ) == 1

    assert reconcile_stale_simulations(
        db_path,
        queue_timeout_seconds=60,
        heartbeat_timeout_seconds=60,
    ) == 1
    assert get_simulation(db_path, stale_id)["status"] == "failed"


def test_save_and_get_results_with_sources(db_path):
    sim_id = "test-sources-001"
    create_simulation(db_path, sim_id, "test", "English", {}, "tech")
    raw_items = [
        {"id": "item-1", "title": "Test Repo", "source": "github",
         "url": "https://github.com/test/repo", "score": 0.9, "text": "A test repo"},
        {"id": "item-2", "title": "Test Paper", "source": "arxiv",
         "url": "https://arxiv.org/abs/1234", "score": 0.7, "text": "A test paper"},
    ]
    save_sim_results(
        db_path, sim_id,
        posts={"hackernews": []},
        personas={"hackernews": []},
        report_json={"verdict": "positive"},
        report_md="## Report",
        raw_items=raw_items,
    )
    result = get_sim_results(db_path, sim_id)
    assert isinstance(result["sources_json"], list)
    assert len(result["sources_json"]) == 2
    assert result["sources_json"][0]["source"] == "github"
    assert result["sources_json"][1]["title"] == "Test Paper"


def test_get_results_sources_json_defaults_to_empty_list(db_path):
    """Old records without sources_json should return [] not raise an error."""
    sim_id = "test-sources-002"
    create_simulation(db_path, sim_id, "test", "English", {}, "tech")
    save_sim_results(
        db_path, sim_id,
        posts={},
        personas={},
        report_json={},
        report_md="",
    )
    result = get_sim_results(db_path, sim_id)
    assert result["sources_json"] == []
