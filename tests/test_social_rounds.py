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


FAKE_ONTOLOGY = {
    "domain_summary": "SaaS tools",
    "entities": [{"id": "e0", "name": "SaaS", "type": "concept", "source_node_ids": []}],
    "relationships": [],
    "market_tensions": ["build vs buy"],
    "key_trends": [],
}

@pytest.mark.asyncio
async def test_decide_action_accepts_ontology():
    """decide_action should accept ontology kwarg."""
    import inspect
    from backend.simulation.social_rounds import decide_action
    sig = inspect.signature(decide_action)
    assert 'ontology' in sig.parameters

@pytest.mark.asyncio
async def test_generate_content_accepts_ontology():
    """generate_content should accept ontology kwarg."""
    import inspect
    from backend.simulation.social_rounds import generate_content
    sig = inspect.signature(generate_content)
    assert 'ontology' in sig.parameters


def test_platform_state_has_recent_speakers_field():
    """PlatformState must have a recent_speakers dict field defaulting to empty."""
    from backend.simulation.models import PlatformState
    state = PlatformState(platform_name="hackernews")
    assert hasattr(state, "recent_speakers")
    assert isinstance(state.recent_speakers, dict)
    assert len(state.recent_speakers) == 0


def test_select_active_agents_cooldown_reduces_recent_speaker_weight():
    """Agents who spoke in the previous round should have weight reduced to 0.1x."""
    from backend.simulation.models import Persona
    from backend.simulation.social_rounds import select_active_agents

    def make_persona(node_id):
        return Persona(
            node_id=node_id, name=f"Agent {node_id}", role="Engineer", age=30,
            seniority="mid", affiliation="individual", company="Corp",
            mbti="INTJ", interests=["AI"], skepticism=5,
            commercial_focus=5, innovation_openness=5, source_title="",
        )

    # 10명 페르소나, 전원 동일 degree=1
    personas = [make_persona(f"n{i}") for i in range(10)]
    degree = {p.node_id: 1 for p in personas}

    # n0이 직전 라운드(round 5)에 발언
    recent_speakers = {"n0": 5}

    # 충분한 반복으로 확률 추정
    selections = []
    for _ in range(1000):
        selected = select_active_agents(
            personas, degree,
            activation_rate=0.3,
            recent_speakers=recent_speakers,
            current_round=6,
        )
        selections.append([p.node_id for p in selected])

    n0_count = sum(1 for s in selections if "n0" in s)
    other_avg = sum(
        sum(1 for s in selections if f"n{i}" in s)
        for i in range(1, 10)
    ) / 9

    # n0 선택 횟수는 다른 에이전트 평균의 20% 이하여야 함 (0.1x weight 반영)
    assert n0_count < other_avg * 0.3, (
        f"n0 should be selected much less frequently: n0={n0_count}, other_avg={other_avg:.1f}"
    )


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
    result = select_active_agents(personas, None, activation_rate=0.5, recent_speakers=None)
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
        personas, None, activation_rate=1.0,
        recent_speakers=recent_speakers, current_round=6,
    )
    assert len(result) >= 1
