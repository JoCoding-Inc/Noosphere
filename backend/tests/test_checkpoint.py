import json
import pytest
import tempfile
from pathlib import Path
from backend.db import init_db, save_checkpoint, get_checkpoint, delete_checkpoint


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    init_db(path)
    yield path
    path.unlink(missing_ok=True)


def test_get_checkpoint_returns_none_when_missing(db_path):
    assert get_checkpoint(db_path, "nonexistent") is None


def test_save_and_get_checkpoint(db_path):
    save_checkpoint(
        db_path,
        sim_id="sim-1",
        last_round=3,
        platform_states={"hackernews": {"platform_name": "hackernews", "round_num": 3, "recent_speakers": {}, "posts": []}},
        personas={"hackernews": [{"node_id": "n1", "name": "Alice", "role": "engineer", "age": 30,
                                   "seniority": "senior", "affiliation": "startup", "company": "Acme",
                                   "mbti": "INTJ", "interests": ["AI"], "skepticism": 5,
                                   "commercial_focus": 5, "innovation_openness": 7, "source_title": "HN post"}]},
        context_nodes=[{"id": "c1", "title": "Test", "source": "input_text", "abstract": "abc"}],
        domain="ai_tools",
        analysis_md="## Analysis",
        ontology={"nodes": []},
        raw_items=[],
    )
    cp = get_checkpoint(db_path, "sim-1")
    assert cp is not None
    assert cp["last_round"] == 3
    assert cp["domain"] == "ai_tools"
    assert cp["platform_states"]["hackernews"]["round_num"] == 3
    assert cp["personas"]["hackernews"][0]["name"] == "Alice"
    assert cp["context_nodes"][0]["id"] == "c1"
    assert cp["ontology"] == {"nodes": []}
    assert cp["raw_items"] == []


def test_save_checkpoint_overwrites_previous(db_path):
    for round_num in [1, 2, 3]:
        save_checkpoint(db_path, "sim-1", round_num, {}, {}, [], "domain", "", None, [])
    cp = get_checkpoint(db_path, "sim-1")
    assert cp["last_round"] == 3


def test_delete_checkpoint(db_path):
    save_checkpoint(db_path, "sim-1", 1, {}, {}, [], "domain", "", None, [])
    delete_checkpoint(db_path, "sim-1")
    assert get_checkpoint(db_path, "sim-1") is None


def test_delete_nonexistent_checkpoint_is_noop(db_path):
    delete_checkpoint(db_path, "nonexistent")  # should not raise


def test_checkpoint_ontology_null(db_path):
    save_checkpoint(db_path, "sim-1", 1, {}, {}, [], "domain", "", None, [])
    cp = get_checkpoint(db_path, "sim-1")
    assert cp["ontology"] is None
