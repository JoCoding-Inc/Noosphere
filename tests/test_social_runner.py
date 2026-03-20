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
