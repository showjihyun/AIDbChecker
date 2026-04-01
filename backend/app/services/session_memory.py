# Spec: FS-DBA-004
"""DBA Agent Session Memory — Valkey-backed multi-turn conversation store.

Stores structured session data with entity extraction, turn history,
and large data caching for multi-turn DBA conversations.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

SESSION_TTL = 3600  # 1 hour
DATA_TTL = 1800  # 30 min for large data
MAX_TURNS = 20  # 10 user+agent turn pairs
ANSWER_MAX_LEN = 2000

# Table/index name patterns
_TABLE_RE = re.compile(
    r"(?:FROM|JOIN|INTO|UPDATE|TABLE|ON)\s+([a-z_][a-z0-9_]*)", re.IGNORECASE
)
_INDEX_RE = re.compile(
    r"(?:INDEX|idx_)\s*([a-z_][a-z0-9_]*)", re.IGNORECASE
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def _get_client():
    """Get async Valkey client."""
    import redis.asyncio as aioredis

    return aioredis.from_url(settings.VALKEY_URL, socket_timeout=2)


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------


async def load_session(session_id: str) -> dict:
    """Load full session data from Valkey.

    Returns empty session structure if not found.
    """
    try:
        client = await _get_client()
        try:
            raw = await client.get(f"dba:session:{session_id}")
            if raw:
                return json.loads(raw)
        finally:
            await client.aclose()
    except Exception:
        pass

    return _empty_session()


async def save_session(
    session_id: str,
    session_data: dict,
    question: str,
    answer: str,
    intent: str,
    data: dict | None = None,
    instance_id: str | None = None,
    instance_name: str | None = None,
) -> None:
    """Save a conversation turn to Valkey with entity extraction.

    Spec: FS-DBA-004 AC-1~3
    """
    try:
        client = await _get_client()
        try:
            key = f"dba:session:{session_id}"

            # Update metadata
            if instance_id:
                session_data["instance_id"] = instance_id
            if instance_name:
                session_data["instance_name"] = instance_name
            session_data["last_active_at"] = _now_iso()

            # Add user turn
            session_data["turns"].append({
                "role": "user",
                "content": question,
                "timestamp": _now_iso(),
            })

            # Add agent turn (full answer up to 2000 chars)
            agent_turn: dict = {
                "role": "agent",
                "content": answer[:ANSWER_MAX_LEN],
                "intent": intent,
                "timestamp": _now_iso(),
            }

            # AC-2: Cache large data separately
            if data and len(json.dumps(data, default=str)) > 500:
                turn_idx = len(session_data["turns"])
                data_key = f"dba:data:{session_id}:turn_{turn_idx}"
                await client.setex(data_key, DATA_TTL, json.dumps(data, default=str))
                agent_turn["data_key"] = data_key

            session_data["turns"].append(agent_turn)

            # AC-8: Trim to max turns
            session_data["turns"] = session_data["turns"][-MAX_TURNS:]

            # AC-3: Extract entities
            _extract_entities(session_data, question, answer, data)

            # AC-6: Save with TTL refresh
            await client.setex(key, SESSION_TTL, json.dumps(session_data, default=str))

        finally:
            await client.aclose()
    except Exception as exc:
        logger.debug("session_memory.save_failed", error=str(exc))


async def load_turn_data(data_key: str) -> dict | None:
    """Load cached turn data (SQL results, metrics) from Valkey."""
    try:
        client = await _get_client()
        try:
            raw = await client.get(data_key)
            return json.loads(raw) if raw else None
        finally:
            await client.aclose()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Entity Extraction
# ---------------------------------------------------------------------------


def _extract_entities(
    session_data: dict, question: str, answer: str, data: dict | None
) -> None:
    """AC-3: Extract tables, indexes, metrics, SQL from conversation.

    Updates session_data["entities"] in place.
    """
    entities = session_data.setdefault("entities", {
        "tables": [],
        "indexes": [],
        "metrics": [],
        "last_sql": "",
    })

    combined = f"{question} {answer}"

    # Tables
    tables = _TABLE_RE.findall(combined)
    for t in tables:
        t_lower = t.lower()
        # Skip SQL keywords that look like table names
        if t_lower in ("set", "select", "where", "and", "or", "not", "null", "true", "false"):
            continue
        if t_lower not in entities["tables"]:
            entities["tables"].append(t_lower)
    entities["tables"] = entities["tables"][-10:]  # keep last 10

    # Indexes
    indexes = _INDEX_RE.findall(combined)
    for idx in indexes:
        idx_lower = idx.lower()
        if idx_lower not in entities["indexes"]:
            entities["indexes"].append(idx_lower)
    entities["indexes"] = entities["indexes"][-10:]

    # Metrics keywords
    metric_kw = ["cpu", "memory", "connection", "tps", "buffer", "replication", "vacuum", "bloat"]
    for kw in metric_kw:
        if kw in combined.lower() and kw not in entities["metrics"]:
            entities["metrics"].append(kw)
    entities["metrics"] = entities["metrics"][-10:]

    # Last SQL
    if data and data.get("sql"):
        entities["last_sql"] = data["sql"][:500]


# ---------------------------------------------------------------------------
# Context Building
# ---------------------------------------------------------------------------


def build_contextual_prompt(session_data: dict, question: str) -> str:
    """AC-4/7: Build LLM prompt with structured session context.

    Includes entities, recent turns, and the current question.
    """
    if not session_data or not session_data.get("turns"):
        return question

    parts: list[str] = []
    entities = session_data.get("entities", {})

    # Entity summary
    entity_lines = []
    if entities.get("tables"):
        entity_lines.append(f"관련 테이블: {', '.join(entities['tables'][-5:])}")
    if entities.get("indexes"):
        entity_lines.append(f"관련 인덱스: {', '.join(entities['indexes'][-5:])}")
    if entities.get("metrics"):
        entity_lines.append(f"관련 메트릭: {', '.join(entities['metrics'][-5:])}")
    if entities.get("last_sql"):
        entity_lines.append(f"최근 SQL: {entities['last_sql'][:200]}")

    if entity_lines:
        parts.append("[식별된 엔티티]\n" + "\n".join(entity_lines))

    # Recent turns (last 3 pairs = 6 entries)
    recent = session_data["turns"][-6:]
    if recent:
        turn_lines = []
        for t in recent:
            role = "사용자" if t["role"] == "user" else "Agent"
            content = t["content"][:300]
            intent_tag = f" [{t.get('intent','')}]" if t.get("intent") else ""
            turn_lines.append(f"{role}{intent_tag}: {content}")
        parts.append("[최근 대화]\n" + "\n".join(turn_lines))

    parts.append(f"[현재 질문]\n{question}")

    return "\n\n".join(parts)


def resolve_intent_from_context(
    session_data: dict, keyword_intent: str, confident: bool
) -> str:
    """AC-5: Use previous intent flow to resolve ambiguous intents.

    If keyword classification is not confident, use conversation flow to guess.
    """
    if confident:
        return keyword_intent

    turns = session_data.get("turns", [])
    if not turns:
        return keyword_intent

    # Find last agent turn's intent
    prev_intent = None
    for t in reversed(turns):
        if t["role"] == "agent" and t.get("intent"):
            prev_intent = t["intent"]
            break

    if not prev_intent:
        return keyword_intent

    # Flow-based intent resolution
    # analyze → "만들어줘/실행해줘" → execute
    # execute → "확인/효과/결과" → analyze
    # query → "더 보여줘/다른건" → query
    if prev_intent == "analyze" and keyword_intent in ("analyze", "execute"):
        return keyword_intent  # trust keyword if somewhat clear
    if prev_intent == "execute":
        return "analyze"  # after execution, likely checking results
    if prev_intent == "query":
        return "query"  # continue querying

    return keyword_intent


def _empty_session() -> dict:
    return {
        "instance_id": "",
        "instance_name": "",
        "created_at": _now_iso(),
        "last_active_at": _now_iso(),
        "turns": [],
        "entities": {
            "tables": [],
            "indexes": [],
            "metrics": [],
            "last_sql": "",
        },
    }
