import dataclasses
import pytest
import sqlite3
from backend.db import init_db, save_checkpoint, get_checkpoint, delete_checkpoint
from backend.simulation.models import PlatformState, SocialPost
from backend.simulation.social_runner import _restore_platform_states


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


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
        raw_items=[],
    )
    cp = get_checkpoint(db_path, "sim-1")
    assert cp is not None
    assert cp["last_round"] == 3
    assert cp["domain"] == "ai_tools"
    assert cp["platform_states"]["hackernews"]["round_num"] == 3
    assert cp["personas"]["hackernews"][0]["name"] == "Alice"
    assert cp["context_nodes"][0]["id"] == "c1"
    assert cp["raw_items"] == []


def test_save_checkpoint_overwrites_previous(db_path):
    for round_num in [1, 2, 3]:
        save_checkpoint(db_path, "sim-1", round_num, {}, {}, [], "domain", "", [])
    cp = get_checkpoint(db_path, "sim-1")
    assert cp["last_round"] == 3


def test_delete_checkpoint(db_path):
    save_checkpoint(db_path, "sim-1", 1, {}, {}, [], "domain", "", [])
    delete_checkpoint(db_path, "sim-1")
    assert get_checkpoint(db_path, "sim-1") is None


def test_delete_nonexistent_checkpoint_is_noop(db_path):
    delete_checkpoint(db_path, "nonexistent")  # should not raise


def test_init_db_migrates_legacy_sim_checkpoints_schema(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE sim_checkpoints (
            sim_id TEXT PRIMARY KEY,
            last_round INTEGER NOT NULL,
            platform_states_json TEXT NOT NULL,
            personas_json TEXT NOT NULL,
            context_nodes_json TEXT NOT NULL,
            domain TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

    init_db(path)

    conn = sqlite3.connect(path)
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(sim_checkpoints)").fetchall()
    }
    conn.close()

    assert {"analysis_md", "raw_items_json", "saved_at"} <= columns


def test_init_db_drops_ontology_column_from_existing_checkpoints(tmp_path):
    path = tmp_path / "legacy_with_ontology.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE sim_checkpoints (
            sim_id TEXT PRIMARY KEY,
            last_round INTEGER NOT NULL,
            platform_states_json TEXT NOT NULL,
            personas_json TEXT NOT NULL,
            context_nodes_json TEXT NOT NULL,
            domain TEXT NOT NULL,
            analysis_md TEXT NOT NULL DEFAULT '',
            ontology_json TEXT,
            raw_items_json TEXT NOT NULL DEFAULT '[]',
            saved_at TEXT NOT NULL
        );
    """)
    conn.execute(
        """
        INSERT INTO sim_checkpoints (
            sim_id, last_round, platform_states_json, personas_json, context_nodes_json,
            domain, analysis_md, ontology_json, raw_items_json, saved_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "sim-1",
            1,
            "{}",
            "{}",
            '[{"id":"c1"}]',
            "domain",
            "analysis",
            '{"nodes":[]}',
            '[{"source":"hn"}]',
            "2026-01-01T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    init_db(path)

    conn = sqlite3.connect(path)
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(sim_checkpoints)").fetchall()
    }
    conn.close()

    assert "ontology_json" not in columns

    checkpoint = get_checkpoint(path, "sim-1")
    assert checkpoint is not None
    assert checkpoint["context_nodes"] == [{"id": "c1"}]
    assert checkpoint["raw_items"] == [{"source": "hn"}]
    assert "ontology_json" not in checkpoint


def test_get_checkpoint_returns_none_for_corrupted_json(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO sim_checkpoints (
            sim_id, last_round, platform_states_json, personas_json, context_nodes_json,
            domain, analysis_md, raw_items_json, saved_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            "sim-bad",
            1,
            "{bad json",
            "{}",
            "[]",
            "domain",
            "",
            "[]",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    assert get_checkpoint(db_path, "sim-bad") is None


def test_checkpoint_roundtrip_rebuilds_post_index_and_excludes_it_from_json(db_path):
    state = PlatformState(
        platform_name="hackernews",
        posts=[
            SocialPost(
                id="p1",
                platform="hackernews",
                author_node_id="n1",
                author_name="Alice",
                content="Hello",
                action_type="post",
                round_num=0,
            )
        ],
        round_num=1,
    )

    serialized_state = dataclasses.asdict(state)
    assert "post_index" not in serialized_state

    save_checkpoint(
        db_path,
        sim_id="sim-post-index",
        last_round=1,
        platform_states={"hackernews": serialized_state},
        personas={},
        context_nodes=[],
        domain="ai_tools",
        analysis_md="",
        raw_items=[],
    )

    checkpoint = get_checkpoint(db_path, "sim-post-index")
    restored = _restore_platform_states(checkpoint["platform_states"])
    restored_state = restored["hackernews"]

    assert "post_index" not in checkpoint["platform_states"]["hackernews"]
    assert restored_state.post_index["p1"] is restored_state.posts[0]
