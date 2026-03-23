import pytest
from unittest.mock import AsyncMock, patch, MagicMock

FAKE_NODES = [
    {"id": "n1", "title": "SaaS", "source": "input_text", "abstract": "Software as a Service"},
    {"id": "n2", "title": "productivity", "source": "input_text", "abstract": "task management"},
]

@pytest.mark.asyncio
async def test_run_simulation_yields_sim_start():
    """run_simulation with context_nodes emits sim_start event."""
    from backend.simulation.social_runner import run_simulation

    events = []
    async for event in run_simulation(
        input_text="A SaaS app",
        context_nodes=FAKE_NODES,
        domain="saas",
        max_agents=2,
        num_rounds=1,
        platforms=["hackernews"],
        language="English",
    ):
        events.append(event)
        if event["type"] in ("sim_done", "sim_error"):
            break

    types = [e["type"] for e in events]
    assert "sim_start" in types


@pytest.mark.asyncio
async def test_run_simulation_empty_nodes_yields_error():
    """run_simulation with empty context_nodes yields sim_error."""
    from backend.simulation.social_runner import run_simulation

    events = []
    async for event in run_simulation(
        input_text="A SaaS app",
        context_nodes=[],
        domain="saas",
    ):
        events.append(event)

    assert events[0]["type"] == "sim_error"



def test_name_deduplication_assigns_suffix_to_duplicates():
    """collect_personas_for_platform should suffix duplicate names within a platform."""
    from backend.simulation.models import Persona

    def make_persona(node_id, name):
        return Persona(
            node_id=node_id, name=name, role="Engineer", age=30,
            seniority="mid", affiliation="individual", company="Corp",
            mbti="INTJ", interests=["AI"], skepticism=5,
            commercial_focus=5, innovation_openness=5, source_title="",
        )

    # Simulate the results list that collect_personas_for_platform builds
    p1 = make_persona("n1", "Ethan Park")
    p2 = make_persona("n2", "Ethan Park")   # duplicate
    p3 = make_persona("n3", "Daniel Cho")
    p4 = make_persona("n4", "Ethan Park")   # third duplicate

    results = [
        ({"type": "sim_persona", "persona": {"name": "Ethan Park"}}, p1),
        ({"type": "sim_persona", "persona": {"name": "Ethan Park"}}, p2),
        ({"type": "sim_persona", "persona": {"name": "Daniel Cho"}}, p3),
        ({"type": "sim_persona", "persona": {"name": "Ethan Park"}}, p4),
    ]

    from backend.simulation.social_runner import _deduplicate_names
    _deduplicate_names(results)

    assert p1.name == "Ethan Park"
    assert p2.name == "Ethan Park (2)"
    assert p3.name == "Daniel Cho"
    assert p4.name == "Ethan Park (3)"

    # event names must match persona names
    assert results[0][0]["persona"]["name"] == "Ethan Park"
    assert results[1][0]["persona"]["name"] == "Ethan Park (2)"
    assert results[2][0]["persona"]["name"] == "Daniel Cho"
    assert results[3][0]["persona"]["name"] == "Ethan Park (3)"


def test_name_deduplication_handles_none_persona():
    """_deduplicate_names should safely skip entries where persona is None."""
    from backend.simulation.social_runner import _deduplicate_names

    results = [
        ({"type": "sim_persona", "persona": {"name": "Alex"}}, None),
        ({"type": "sim_persona", "persona": {"name": "Alex"}}, None),
    ]
    _deduplicate_names(results)  # should not raise
