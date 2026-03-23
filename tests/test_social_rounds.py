import pytest
from unittest.mock import AsyncMock, patch
from backend.llm import LLMResponse


async def test_generate_seed_post_with_provider():
    tool_args = {"title": "Test Product", "text": "A great SaaS app", "url": "https://example.com", "tags": ["saas"]}
    mock_response = LLMResponse(content=None, tool_name="create_hn_post", tool_args=tool_args)

    with patch("backend.simulation.social_rounds.llm") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_response)
        from backend.simulation.social_rounds import generate_seed_post
        from backend.simulation.platforms.hackernews import HackerNews
        platform = HackerNews()
        post = await generate_seed_post(platform, "A great SaaS app", "English", provider="openai")
    assert post.platform == "hackernews"
    assert post.author_node_id == "__seed__"


async def test_decide_action_with_provider():
    from backend.simulation.models import Persona
    from backend.simulation.platforms.hackernews import HackerNews

    tool_args = {"action_type": "post", "target_post_id": None}
    mock_response = LLMResponse(content=None, tool_name="decide_action", tool_args=tool_args)

    platform = HackerNews()
    persona = Persona(
        node_id="n1", name="Alice", role="engineer", age=30,
        seniority="mid", affiliation="individual", company="Corp", mbti="INTJ",
        interests=["AI"], skepticism=3, commercial_focus=5, innovation_openness=7,
        source_title="AI SaaS",
    )
    allowed = platform.get_allowed_actions(persona)
    tool_args = {"action_type": allowed[0], "target_post_id": None}
    mock_response = LLMResponse(content=None, tool_name="decide_action", tool_args=tool_args)

    with patch("backend.simulation.social_rounds.llm") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_response)
        from backend.simulation.social_rounds import decide_action
        action = await decide_action(persona, platform, "feed text", "English", provider="openai")
    assert action.action_type == allowed[0]



def test_platform_state_has_recent_speakers_field():
    """PlatformState must have a recent_speakers dict field defaulting to empty."""
    from backend.simulation.models import PlatformState
    state = PlatformState(platform_name="hackernews")
    assert hasattr(state, "recent_speakers")
    assert isinstance(state.recent_speakers, dict)
    assert len(state.recent_speakers) == 0



def test_select_active_agents_cooldown_none_behaves_as_before():
    """When recent_speakers=None, behavior matches original (no cooldown)."""
    from backend.simulation.models import Persona
    from backend.simulation.social_rounds import select_active_agents

    personas = [
        Persona(
            node_id=f"n{i}", name=f"Agent {i}", role="Engineer", age=30,
            seniority="mid", affiliation="individual", company="Corp",
            mbti="INTJ", interests=["AI"], skepticism=5,
            commercial_focus=5, innovation_openness=5, source_title="",
        )
        for i in range(5)
    ]
    result = select_active_agents(personas, activation_rate=0.5, recent_speakers=None)
    assert len(result) >= 1
    assert len(result) <= len(personas)


def test_select_active_agents_cooldown_fallback_small_pool():
    """When all agents have cooldown and pool is small, at least 1 agent is returned."""
    from backend.simulation.models import Persona
    from backend.simulation.social_rounds import select_active_agents

    personas = [
        Persona(
            node_id=f"n{i}", name=f"Agent {i}", role="Engineer", age=30,
            seniority="mid", affiliation="individual", company="Corp",
            mbti="INTJ", interests=["AI"], skepticism=5,
            commercial_focus=5, innovation_openness=5, source_title="",
        )
        for i in range(3)
    ]
    # 전원 직전 라운드 발언자
    recent_speakers = {"n0": 5, "n1": 5, "n2": 5}
    result = select_active_agents(
        personas, activation_rate=1.0,
        recent_speakers=recent_speakers, current_round=6,
    )
    assert len(result) >= 1
