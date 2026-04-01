# Spec: FS-DBA-004
"""Tests for DBA Agent Multi-Turn Memory."""

from tests.conftest import spec_ref


@spec_ref("FS-DBA-004", "AC-1")
def test_dba_004_ac1_answer_max_len():
    """AC-1: Answer stored up to 2000 chars."""
    from app.services.session_memory import ANSWER_MAX_LEN

    assert ANSWER_MAX_LEN == 2000


@spec_ref("FS-DBA-004", "AC-2")
def test_dba_004_ac2_data_ttl():
    """AC-2: Large data cached with 30min TTL."""
    from app.services.session_memory import DATA_TTL

    assert DATA_TTL == 1800


@spec_ref("FS-DBA-004", "AC-3")
def test_dba_004_ac3_entity_extraction():
    """AC-3: Entities (tables, indexes, metrics) auto-extracted."""
    from app.services.session_memory import _extract_entities

    session_data = {"entities": {"tables": [], "indexes": [], "metrics": [], "last_sql": ""}}
    _extract_entities(
        session_data,
        "orders 테이블이 느려",
        "SELECT * FROM orders JOIN users ON orders.user_id = users.id 결과 풀스캔 감지. CPU 85%.",
        {"sql": "SELECT * FROM orders"},
    )

    ent = session_data["entities"]
    assert "orders" in ent["tables"]
    assert "users" in ent["tables"]
    assert "cpu" in ent["metrics"]
    assert ent["last_sql"] == "SELECT * FROM orders"


@spec_ref("FS-DBA-004", "AC-4")
def test_dba_004_ac4_contextual_prompt():
    """AC-4: Pronouns resolved via entity context."""
    from app.services.session_memory import build_contextual_prompt

    session_data = {
        "turns": [
            {"role": "user", "content": "orders 테이블 분석해줘"},
            {"role": "agent", "content": "orders 테이블 풀스캔 감지", "intent": "analyze"},
        ],
        "entities": {"tables": ["orders"], "indexes": [], "metrics": ["cpu"], "last_sql": ""},
    }

    result = build_contextual_prompt(session_data, "인덱스 만들어줘")
    assert "orders" in result
    assert "인덱스 만들어줘" in result
    assert "관련 테이블" in result


@spec_ref("FS-DBA-004", "AC-5")
def test_dba_004_ac5_intent_flow():
    """AC-5: Previous intent flow resolves ambiguous intent."""
    from app.services.session_memory import resolve_intent_from_context

    # After execute → ambiguous → analyze (check results)
    session = {
        "turns": [
            {"role": "agent", "content": "인덱스 생성 완료", "intent": "execute"},
        ]
    }
    result = resolve_intent_from_context(session, "analyze", confident=False)
    assert result == "analyze"

    # After query → ambiguous → query (continue)
    session2 = {
        "turns": [
            {"role": "agent", "content": "SQL 결과", "intent": "query"},
        ]
    }
    result2 = resolve_intent_from_context(session2, "analyze", confident=False)
    assert result2 == "query"


@spec_ref("FS-DBA-004", "AC-6")
def test_dba_004_ac6_session_ttl():
    """AC-6: Session TTL is 1 hour."""
    from app.services.session_memory import SESSION_TTL

    assert SESSION_TTL == 3600


@spec_ref("FS-DBA-004", "AC-7")
def test_dba_004_ac7_structured_history():
    """AC-7: Contextual prompt includes entities + recent turns."""
    from app.services.session_memory import build_contextual_prompt

    session = {
        "turns": [
            {"role": "user", "content": "CPU 확인"},
            {"role": "agent", "content": "CPU 45%", "intent": "analyze"},
        ],
        "entities": {"tables": ["orders"], "indexes": ["idx_orders_user_id"], "metrics": ["cpu"], "last_sql": "SELECT 1"},
    }

    prompt = build_contextual_prompt(session, "메모리는?")
    assert "식별된 엔티티" in prompt
    assert "최근 대화" in prompt
    assert "현재 질문" in prompt


@spec_ref("FS-DBA-004", "AC-8")
def test_dba_004_ac8_max_turns():
    """AC-8: Max 20 entries (10 turn pairs)."""
    from app.services.session_memory import MAX_TURNS

    assert MAX_TURNS == 20
