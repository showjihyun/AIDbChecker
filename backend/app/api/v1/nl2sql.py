# Spec: FR-AI-003, MVP-AI-004
"""NL2SQL API — natural language to SQL conversion and read-only execution.

POST /api/v1/nl2sql/query converts a user's natural language question into
a PostgreSQL SELECT query, executes it read-only, and returns the results.
Auth required: operator, db_admin, or super_admin.
"""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_role
from app.models.nl2sql_history import NL2SQLHistory
from app.models.user import User
from app.schemas.nl2sql import NL2SQLQueryRequest, NL2SQLQueryResponse
from app.services import nl2sql as nl2sql_service

logger = structlog.get_logger(__name__)

router = APIRouter()


# Spec: FR-AI-003 — NL2SQL query endpoint (operator+ required)
@router.post(
    "/nl2sql/query",
    response_model=NL2SQLQueryResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Convert natural language to SQL and execute",
    description="Translates a natural language question into a PostgreSQL SELECT query, "
    "executes it read-only against the system DB, and returns the results.",
)
async def nl2sql_query(
    body: NL2SQLQueryRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> NL2SQLQueryResponse:
    """Natural language to SQL: question -> SQL -> read-only execution -> results.

    Safety guarantees:
    - Only SELECT queries are generated and executed
    - statement_timeout = 5 seconds
    - default_transaction_read_only = on
    - Results capped at 1000 rows
    """
    # Step 1: Generate SQL from natural language
    try:
        sql = await nl2sql_service.generate_sql(
            question=body.question,
            instance_id=body.instance_id,
        )
    except ValueError as exc:
        # Write operation detected in generated SQL
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except RuntimeError as exc:
        # LLM call failed
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    # Step 2: Execute the read-only SQL
    warning = None
    try:
        columns, rows, execution_time_ms = await nl2sql_service.execute_readonly_sql(
            session=session,
            sql=sql,
            timeout_seconds=5,
            max_rows=1000,
        )
    except RuntimeError as exc:
        # SQL execution failed — return the SQL but no results
        logger.warning(
            "nl2sql.execution_failed",
            sql=sql[:200],
            error=str(exc),
        )
        model_name = nl2sql_service.get_model_name()
        # Save failed attempt to history
        await _save_history(
            session, current_user.id, body.instance_id,
            body.question, sql, None, model_name,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="SQL execution failed. Try rephrasing your question.",
        )

    if len(rows) >= 1000:
        warning = "Results truncated to 1000 rows. Add more specific filters."

    model_name = nl2sql_service.get_model_name()

    # Step 3: Save to history
    execution_result = {"rows": len(rows), "columns": columns}
    await _save_history(
        session, current_user.id, body.instance_id,
        body.question, sql, execution_result, model_name,
    )

    return NL2SQLQueryResponse(
        sql=sql,
        result_rows=rows,
        result_columns=columns,
        execution_time_ms=execution_time_ms,
        ai_model=model_name,
        warning=warning,
    )


async def _save_history(
    session: AsyncSession,
    user_id: UUID,
    instance_id: UUID,
    question: str,
    sql: str,
    execution_result: dict | None,
    model_name: str,
) -> None:
    """Persist NL2SQL query to history table for continuous improvement."""
    try:
        history = NL2SQLHistory(
            user_id=user_id,
            instance_id=instance_id,
            natural_query=question,
            generated_sql=sql,
            execution_result=execution_result,
            ai_model=model_name,
        )
        session.add(history)
        await session.commit()
    except Exception as exc:
        logger.error("nl2sql.history_save_failed", error=str(exc))
        # Non-critical — don't fail the request
        await session.rollback()
