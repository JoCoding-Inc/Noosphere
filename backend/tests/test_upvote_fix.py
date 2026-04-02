"""
업보트 + 코멘트 동시 수행 검증 테스트

수정된 platform_round 로직:
  - 에이전트가 vote 액션을 선택하면 → 업보트 적용 AND 코멘트 생성 (둘 다)
  - 에이전트가 content 액션을 선택하면 → 코멘트만 생성
"""
from __future__ import annotations
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.simulation.models import Persona, SocialPost, PlatformState
from backend.simulation.platforms.base import AbstractPlatform, AgentAction


# ── 헬퍼: 테스트용 최소 Persona ───────────────────────────────────────────────

def make_persona(node_id: str = "p1") -> Persona:
    return Persona(
        node_id=node_id,
        name="Test User",
        role="developer",
        age=30,
        seniority="mid",
        affiliation="startup",
        company="TestCo",
        mbti="INTJ",
        interests=["tech"],
        skepticism=5,
        commercial_focus=5,
        innovation_openness=5,
        source_title="test",
    )


# ── 헬퍼: 테스트용 최소 Platform ──────────────────────────────────────────────

class MockPlatform(AbstractPlatform):
    name = "test_platform"
    allowed_actions = ["comment", "upvote"]
    no_content_actions = {"upvote"}
    system_prompt = "test"

    def build_feed(self, state, **kwargs) -> str:  # type: ignore[override]
        return "feed"


# ── 테스트 ────────────────────────────────────────────────────────────────────

def collect(gen):
    """비동기 제너레이터 → 이벤트 리스트"""
    async def _run():
        return [e async for e in gen]
    return asyncio.run(_run())


@pytest.mark.asyncio
async def test_upvote_action_also_generates_comment():
    """
    에이전트가 upvote를 선택했을 때
    1) 업보트가 target post에 적용되어야 함
    2) 추가로 코멘트 포스트도 생성되어야 함
    """
    from backend.simulation.social_rounds import platform_round

    platform = MockPlatform()
    state = PlatformState(platform_name="test_platform")
    persona = make_persona()

    # 기존 포스트 (업보트 대상)
    seed = SocialPost(
        id="seed-1", platform="test_platform",
        author_node_id="__seed__", author_name="Noosphere",
        content="Seed post", action_type="post", round_num=0,
    )
    state.add_post(seed)

    # decide_action → upvote 선택
    # generate_content → 코멘트 텍스트 반환
    with patch(
        "backend.simulation.social_rounds.decide_action",
        new=AsyncMock(return_value=AgentAction(action_type="upvote", target_post_id="seed-1")),
    ), patch(
        "backend.simulation.social_rounds.generate_content",
        new=AsyncMock(return_value=("Great idea! This is a really compelling and well-thought-out concept.", {})),
    ), patch(
        "backend.simulation.social_rounds.random.random",
        return_value=0.0,  # 항상 threshold 미만 → 콘텐츠 생성 강제
    ):
        events = [e async for e in platform_round(
            platform, state, [persona],
            idea_text="test idea", round_num=1, language="English",
            activation_rate=1.0,
        )]

    event_types = [e["type"] for e in events]

    # 업보트 이벤트가 있어야 함
    assert "sim_platform_reaction" in event_types, \
        f"업보트 이벤트 없음. 발생한 이벤트: {event_types}"

    # 코멘트 포스트 이벤트도 있어야 함
    assert "sim_platform_post" in event_types, \
        f"코멘트 포스트 이벤트 없음. 발생한 이벤트: {event_types}"

    # seed-1의 upvotes가 1이어야 함
    updated_seed = state.get_post("seed-1")
    assert updated_seed is not None
    assert updated_seed.upvotes == 1, \
        f"업보트 미적용. seed-1.upvotes = {updated_seed.upvotes}"

    # 새 포스트가 state에 추가되어야 함 (seed + 새 코멘트)
    assert len(state.posts) == 2, \
        f"코멘트 미생성. posts 수 = {len(state.posts)}"


@pytest.mark.asyncio
async def test_comment_action_only_generates_post():
    """
    에이전트가 comment를 선택했을 때
    1) 코멘트만 생성되어야 함
    2) 업보트 이벤트는 없어야 함
    """
    from backend.simulation.social_rounds import platform_round

    platform = MockPlatform()
    state = PlatformState(platform_name="test_platform")
    persona = make_persona()

    seed = SocialPost(
        id="seed-1", platform="test_platform",
        author_node_id="__seed__", author_name="Noosphere",
        content="Seed post", action_type="post", round_num=0,
    )
    state.add_post(seed)

    with patch(
        "backend.simulation.social_rounds.decide_action",
        new=AsyncMock(return_value=AgentAction(action_type="comment", target_post_id="seed-1")),
    ), patch(
        "backend.simulation.social_rounds.generate_content",
        new=AsyncMock(return_value=("Interesting concept! This approach seems very promising and worth exploring further.", {})),
    ):
        events = [e async for e in platform_round(
            platform, state, [persona],
            idea_text="test idea", round_num=1, language="English",
            activation_rate=1.0,
        )]

    event_types = [e["type"] for e in events]

    # 코멘트는 있어야 함
    assert "sim_platform_post" in event_types, \
        f"코멘트 포스트 이벤트 없음. 발생한 이벤트: {event_types}"

    # 업보트 이벤트는 없어야 함
    assert "sim_platform_reaction" not in event_types, \
        f"불필요한 업보트 이벤트 발생. 발생한 이벤트: {event_types}"

    # seed의 upvotes는 여전히 0
    updated_seed = state.get_post("seed-1")
    assert updated_seed.upvotes == 0, \
        f"의도하지 않은 업보트. seed-1.upvotes = {updated_seed.upvotes}"
