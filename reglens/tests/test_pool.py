"""
Live Neon round-trip smoke test.
Mirrors the manual verification run against the reglens Neon project:
session -> finding -> provisions -> finding_log -> audit_log.

Skipped automatically when DATABASE_URL is not set (CI without secrets).
Run: pytest tests/test_pool.py -v
"""
import os
import uuid

import pytest

requires_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — live Neon test skipped",
)

TEST_USER_UID = "00000000-0000-0000-0000-00000000c0de"


@requires_db
@pytest.mark.asyncio
async def test_pool_lazy_init():
    """Pool initialises lazily — no FastAPI lifespan required."""
    from agent.clients import get_pg_pool, close_pg_pool

    pool = await get_pg_pool()
    assert pool is not None
    result = await pool.fetchval("SELECT 1")
    assert result == 1
    await close_pg_pool()


@requires_db
@pytest.mark.asyncio
async def test_session_round_trip():
    """Full write/read: session -> finding -> provisions -> logs, then cleanup."""
    from agent.clients import get_pg_pool, close_pg_pool
    from agent.db_utils import (
        upsert_user,
        create_session,
        get_session,
        save_finding,
        update_finding_status,
        get_session_findings,
        write_audit_log,
        update_session_status,
    )

    pool = await get_pg_pool()
    # Composite session id: {user_uuid}~{uuid}; DB stores only the suffix
    session_uuid = str(uuid.uuid4())
    session_id   = f"{TEST_USER_UID}~{session_uuid}"

    try:
        # 1. User + session
        await upsert_user(pool, TEST_USER_UID, "test@reglens.local")
        sid = await create_session(pool, TEST_USER_UID, "Test sludge query", session_id)
        assert sid == session_uuid

        sess = await get_session(pool, session_id)
        assert sess is not None
        assert sess["title"] == "Test sludge query"

        # 2. Finding + provisions + link rows
        finding_uid = await save_finding(pool, session_id, {
            "title":                  "Test Horizontal Sludge Finding",
            "sludge_type":            "horizontal",
            "severity":               "high",
            "recommended_action":     "consolidate",
            "rationale":              "Two bodies require identical data with different field names.",
            "confidence_score":       0.87,
            "cross_cutting":          True,
            "estimated_burden":       "~20 person-days/year",
            "source_provisions":      ["FATF Rec 10 (a)", "BoN AML Reg Section 4.1"],
            "overlapping_provisions": ["ESAAMLG Guideline 3.2"],
            "affected_domains":       ["AML/CFT"],
        })
        assert finding_uid

        # 3. Status update writes entity + finding_log (two operations, no trigger)
        await update_finding_status(
            pool, finding_uid, "approved",
            user_uid=TEST_USER_UID, session_id=session_id,
            notes="Approved in round-trip test",
        )

        # 4. Read back via link tables
        findings = await get_session_findings(pool, session_id)
        assert len(findings) == 1
        assert findings[0]["title"] == "Test Horizontal Sludge Finding"
        assert findings[0]["status"] == "approved"
        assert len(findings[0]["source_provisions"]) == 2
        assert len(findings[0]["overlapping_provisions"]) == 1

        # 5. Audit log + session status
        await write_audit_log(
            pool, session_id,
            "Round trip verified", "test",
            status_from="active", status_to="complete",
            user_uid=TEST_USER_UID,
        )
        await update_session_status(pool, session_id, "complete", "approved")
        sess = await get_session(pool, session_id)
        assert sess["status"] == "complete"

    finally:
        # Cleanup — delete provisions via links BEFORE deleting the links
        await pool.execute(
            """
            DELETE FROM provision WHERE provision_uid IN (
                SELECT provision_uid FROM finding_provision
                WHERE finding_uid IN (
                    SELECT finding_uid FROM session_finding WHERE session_uid = $1
                )
            )
            """,
            session_uuid,
        )
        await pool.execute(
            """
            DELETE FROM finding_provision WHERE finding_uid IN (
                SELECT finding_uid FROM session_finding WHERE session_uid = $1
            )
            """,
            session_uuid,
        )
        await pool.execute(
            """
            DELETE FROM finding WHERE finding_uid IN (
                SELECT finding_uid FROM session_finding WHERE session_uid = $1
            )
            """,
            session_uuid,
        )
        await pool.execute("DELETE FROM finding_log     WHERE session_uid = $1", session_uuid)
        await pool.execute("DELETE FROM audit_log       WHERE session_uid = $1", session_uuid)
        await pool.execute("DELETE FROM session_finding WHERE session_uid = $1", session_uuid)
        await pool.execute("DELETE FROM session         WHERE session_uid = $1", session_uuid)
        await pool.execute("DELETE FROM user_account    WHERE user_uid    = $1", TEST_USER_UID)
        await close_pg_pool()
