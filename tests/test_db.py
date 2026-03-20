import pytest
import tempfile
import os
from backend.db import init_db, create_simulation, update_simulation_status, \
    save_sim_results, get_sim_results, list_history, get_simulation

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
