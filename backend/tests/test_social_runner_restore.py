from backend.simulation.models import Persona, PlatformState, SocialPost
from backend.simulation.social_runner import _restore_personas, _restore_platform_states


PERSONA_DICT = {
    "hackernews": [
        {
            "node_id": "n1", "name": "Alice", "role": "engineer", "age": 30,
            "seniority": "senior", "affiliation": "startup", "company": "Acme",
            "mbti": "INTJ", "interests": ["AI", "OSS"], "skepticism": 4,
            "commercial_focus": 3, "innovation_openness": 8, "source_title": "HN post"
        }
    ]
}

POST_DICT = {
    "hackernews": {
        "platform_name": "hackernews",
        "round_num": 2,
        "recent_speakers": {"n1": 1},
        "posts": [
            {
                "id": "p1", "platform": "hackernews", "author_node_id": "n1",
                "author_name": "Alice", "content": "Hello", "action_type": "post",
                "round_num": 0, "upvotes": 5, "downvotes": 0, "parent_id": None,
                "structured_data": {"url": "http://example.com"}
            }
        ]
    }
}


def test_restore_personas_returns_persona_instances():
    result = _restore_personas(PERSONA_DICT)
    assert "hackernews" in result
    personas = result["hackernews"]
    assert len(personas) == 1
    p = personas[0]
    assert isinstance(p, Persona)
    assert p.name == "Alice"
    assert p.age == 30
    assert p.source_title == "HN post"
    # generation is a property, not stored — but should still work
    assert p.generation == "Millennial"


def test_restore_personas_excludes_generation_from_constructor():
    # Confirm we don't try to pass 'generation' as a kwarg (it's a property)
    # If this test passes, no TypeError was raised
    result = _restore_personas(PERSONA_DICT)
    assert result["hackernews"][0].interests == ["AI", "OSS"]


def test_restore_platform_states_returns_platform_state_instances():
    result = _restore_platform_states(POST_DICT)
    assert "hackernews" in result
    state = result["hackernews"]
    assert isinstance(state, PlatformState)
    assert state.platform_name == "hackernews"
    assert state.round_num == 2
    assert state.recent_speakers == {"n1": 1}


def test_restore_platform_states_restores_posts():
    result = _restore_platform_states(POST_DICT)
    posts = result["hackernews"].posts
    assert len(posts) == 1
    post = posts[0]
    assert isinstance(post, SocialPost)
    assert post.id == "p1"
    assert post.structured_data == {"url": "http://example.com"}
    assert post.parent_id is None


def test_restore_platform_states_empty():
    result = _restore_platform_states({})
    assert result == {}


def test_restore_personas_empty():
    result = _restore_personas({})
    assert result == {}


def test_restore_helpers_tolerate_missing_optional_fields():
    restored_personas = _restore_personas({
        "hackernews": [{
            "node_id": "n2",
            "name": "Bob",
            "role": "founder",
            "age": "27",
        }]
    })
    restored_states = _restore_platform_states({
        "hackernews": {
            "posts": [{
                "id": "p2",
                "author_name": "Bob",
                "content": "Hi",
            }],
        }
    })

    assert restored_personas["hackernews"][0].generation == "Gen Z"
    assert restored_personas["hackernews"][0].interests == []
    assert restored_states["hackernews"].platform_name == "hackernews"
    assert restored_states["hackernews"].posts[0].platform == "hackernews"
    assert restored_states["hackernews"].posts[0].action_type == "post"
