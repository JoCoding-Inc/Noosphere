from __future__ import annotations
import dataclasses


@dataclasses.dataclass
class Persona:
    node_id: str
    name: str
    role: str
    age: int
    seniority: str          # "intern" | "junior" | "mid" | "senior" | "lead" | "principal" | "director" | "vp" | "c_suite"
    affiliation: str        # "individual" | "startup" | "mid_size" | "enterprise" | "bigtech" | "academic"
    company: str            # e.g. "Google", "seed-stage fintech startup", "MIT research lab"
    mbti: str
    interests: list[str]
    skepticism: int         # 1-10: 1=enthusiastic evangelist, 10=extreme skeptic
    commercial_focus: int   # 1-10: 1=idealistic/academic, 10=purely commercial
    innovation_openness: int  # 1-10: 1=very conservative, 10=early adopter
    source_title: str
    domain_type: str = ""
    tech_area: list[str] = dataclasses.field(default_factory=list)
    market: list[str] = dataclasses.field(default_factory=list)
    problem_domain: list[str] = dataclasses.field(default_factory=list)

    @property
    def generation(self) -> str:
        if self.age <= 28:
            return "Gen Z"
        elif self.age <= 44:
            return "Millennial"
        elif self.age <= 60:
            return "Gen X"
        else:
            return "Boomer"

    def bias_description(self) -> str:
        """Human-readable summary of bias dimensions for use in prompts."""
        skeptic_label = (
            "enthusiastic evangelist" if self.skepticism <= 2 else
            "optimistic supporter" if self.skepticism <= 4 else
            "balanced evaluator" if self.skepticism <= 6 else
            "critical skeptic" if self.skepticism <= 8 else
            "extreme skeptic"
        )
        commercial_label = (
            "academic/idealistic" if self.commercial_focus <= 2 else
            "mostly idealistic" if self.commercial_focus <= 4 else
            "balanced" if self.commercial_focus <= 6 else
            "commercially driven" if self.commercial_focus <= 8 else
            "purely ROI-focused"
        )
        innovation_label = (
            "very conservative" if self.innovation_openness <= 2 else
            "cautious" if self.innovation_openness <= 4 else
            "pragmatic" if self.innovation_openness <= 6 else
            "early adopter" if self.innovation_openness <= 8 else
            "extreme risk-taker"
        )
        return (
            f"skepticism {self.skepticism}/10 ({skeptic_label}), "
            f"commercial focus {self.commercial_focus}/10 ({commercial_label}), "
            f"innovation openness {self.innovation_openness}/10 ({innovation_label})"
        )


@dataclasses.dataclass
class SocialPost:
    id: str                        # uuid4 또는 "__seed__{platform}"
    platform: str                  # "hackernews" | "producthunt" | "indiehackers" | "reddit_startups" | "linkedin"
    author_node_id: str            # 에이전트 node_id 또는 "__seed__"
    author_name: str
    content: str
    action_type: str               # 플랫폼별 허용 action_type
    round_num: int                 # 0 = 씨드, 1~N = 시뮬레이션 라운드
    upvotes: int = 0
    downvotes: int = 0
    parent_id: str | None = None   # None = 최상위; 댓글/답글은 부모 post id
    structured_data: dict = dataclasses.field(default_factory=dict)  # platform-specific structured fields


@dataclasses.dataclass
class PlatformState:
    platform_name: str
    posts: list[SocialPost] = dataclasses.field(default_factory=list)
    round_num: int = 0
    recent_speakers: dict[str, int] = dataclasses.field(default_factory=dict)
    # node_id → 마지막 콘텐츠(comment/reply) 생성 round_num. vote/react는 기록 안 함.

    def __post_init__(self) -> None:
        # post_index는 dataclass 필드가 아닌 일반 속성으로 관리하여
        # dataclasses.asdict() 직렬화에서 자동 제외됩니다.
        self.rebuild_post_index()

    def rebuild_post_index(self) -> None:
        self.post_index: dict[str, SocialPost] = {post.id: post for post in self.posts}

    def add_post(self, post: SocialPost) -> None:
        self.posts.append(post)
        self.post_index[post.id] = post

    def get_post(self, post_id: str) -> SocialPost | None:
        post_index = getattr(self, "post_index", None)
        if not isinstance(post_index, dict) or len(post_index) != len(self.posts):
            self.rebuild_post_index()
            post_index = self.post_index

        post = post_index.get(post_id)
        if post is None and self.posts:
            # Repair stale caches caused by out-of-band list mutation before giving up.
            self.rebuild_post_index()
            post = self.post_index.get(post_id)
        return post
