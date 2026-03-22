import asyncio
import json

import pytest

from backend import main
from backend import db
from backend.db import create_simulation, init_db, save_checkpoint, update_simulation_status


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    init_db(path)
    monkeypatch.setattr(main, "DB_PATH", path)
    monkeypatch.setattr(main, "get_simulation", db.get_simulation)
    monkeypatch.setattr(main, "get_checkpoint", db.get_checkpoint)
    monkeypatch.setattr(main, "update_simulation_status", db.update_simulation_status)
    monkeypatch.setattr(main, "count_active_simulations", db.count_active_simulations)
    monkeypatch.setattr(main, "reconcile_stale_simulations", db.reconcile_stale_simulations)
    return path


def test_simulation_status_includes_checkpoint_round(db_path):
    sim_id = "sim-status"
    create_simulation(
        db_path,
        sim_id,
        "Idea",
        "English",
        {"input_text": "Idea", "language": "English"},
        "",
    )
    update_simulation_status(db_path, sim_id, "failed", allowed_current_statuses={"running"})
    save_checkpoint(db_path, sim_id, 4, {}, {}, [], "domain", "", None, [])

    response = asyncio.run(main.simulation_status(sim_id))

    assert response == {
        "status": "failed",
        "last_round": 4,
        "has_checkpoint": True,
    }


def test_resume_simulation_reuses_sim_id_as_task_id(db_path, monkeypatch):
    sim_id = "sim-resume"
    create_simulation(
        db_path,
        sim_id,
        "Idea",
        "English",
        {
            "input_text": "Idea",
            "language": "English",
            "num_rounds": 12,
            "max_agents": 50,
            "platforms": ["hackernews"],
            "activation_rate": 0.25,
            "provider": "openai",
        },
        "",
    )
    update_simulation_status(db_path, sim_id, "failed", allowed_current_statuses={"running"})
    save_checkpoint(db_path, sim_id, 2, {}, {}, [], "domain", "", None, [])

    captured: dict[str, object] = {}

    def fake_apply_async(*, args, task_id):
        captured["args"] = args
        captured["task_id"] = task_id

    monkeypatch.setattr(main.run_simulation_task, "apply_async", fake_apply_async)

    response = asyncio.run(main.resume_simulation(sim_id))

    assert response == {"sim_id": sim_id, "resuming_from_round": 3}
    assert captured["task_id"] == sim_id
    assert captured["args"] == [sim_id, json.loads(main.get_simulation(db_path, sim_id)["config_json"])]


def test_simulate_stream_rejects_invalid_last_id(db_path):
    sim_id = "sim-stream"
    create_simulation(
        db_path,
        sim_id,
        "Idea",
        "English",
        {"input_text": "Idea", "language": "English"},
        "",
    )

    with pytest.raises(main.HTTPException) as excinfo:
        asyncio.run(main.simulate_stream(sim_id, None, last_id="not-a-stream-id"))

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Invalid last_id"
