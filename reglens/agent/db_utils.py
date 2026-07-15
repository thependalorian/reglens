"""
Database utilities for RegLens — Neon Postgres via asyncpg.

Ketchup DEV design principles (Wiebe Geldenhuys, Jul 7 2026):
  - UUIDs from application (uuid.uuid4()) — never DB-generated
  - No FK constraints — relationships enforced here
  - Link tables inserted/queried explicitly
  - Status updated in application — no triggers
  - 'description' aliased to meaningful names in SELECT
  - Entity table = current state, log table = full history

Session identity: the API session_id is '{user_uid}~{uuid}'.
UUID-typed columns store the UUID suffix — session_db_uid() converts.
"""
from __future__ import annotations
import uuid
from typing import List, Optional

import asyncpg


def new_uid() -> str:
    """UUID from application — Wiebe: 'not done by the database side itself'"""
    return str(uuid.uuid4())


def session_db_uid(session_id: str) -> str:
    """Composite session id '{user_uid}~{uuid}' → UUID part for UUID columns."""
    return session_id.split("~", 1)[-1]


def _uuid_or_none(value: str) -> Optional[str]:
    """Coerce non-UUID actor ids (e.g. 'system') to NULL for UUID columns."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


# ============================================================
# USER
# ============================================================

async def upsert_user(
    pool:       asyncpg.Pool,
    user_uid:   str,
    email:      str,
    user_type:  str = "analyst",
) -> None:
    """Application creates user — no trigger, no DB-side upsert (no PK)."""
    exists = await pool.fetchval(
        "SELECT 1 FROM user_account WHERE user_uid = $1", user_uid
    )
    if not exists:
        await pool.execute(
            """
            INSERT INTO user_account
                (user_uid, description, email, user_type, status)
            VALUES ($1, $2, $3, $4, 'active')
            """,
            user_uid, email.split("@")[0], email, user_type,
        )


# ============================================================
# SESSION
# ============================================================

async def create_session(
    pool:       asyncpg.Pool,
    user_uid:   str,
    query:      str,
    session_id: str,
) -> str:
    """Insert session row keyed by the UUID part of the composite session id."""
    session_uid = session_db_uid(session_id)
    exists = await pool.fetchval(
        "SELECT 1 FROM session WHERE session_uid = $1", session_uid
    )
    if not exists:
        await pool.execute(
            """
            INSERT INTO session
                (session_uid, user_uid, description, query,
                 approval_status, status)
            VALUES ($1, $2, $3, $4, 'pending', 'active')
            """,
            session_uid, user_uid, query[:120], query,
        )
    return session_uid


async def update_session_status(
    pool:             asyncpg.Pool,
    session_id:       str,
    status:           str,
    approval_status:  Optional[str] = None,
) -> None:
    """Status updated by application — no trigger (Wiebe: 'let the system update')"""
    session_uid = session_db_uid(session_id)
    if approval_status:
        await pool.execute(
            "UPDATE session SET status = $2, approval_status = $3 WHERE session_uid = $1",
            session_uid, status, approval_status,
        )
    else:
        await pool.execute(
            "UPDATE session SET status = $2 WHERE session_uid = $1",
            session_uid, status,
        )


async def get_session(pool: asyncpg.Pool, session_id: str) -> Optional[dict]:
    row = await pool.fetchrow(
        """
        SELECT session_uid, description AS title, query,
               approval_status, status, user_uid
        FROM session
        WHERE session_uid = $1
        """,
        session_db_uid(session_id),
    )
    if row is None:
        return None
    data = dict(row)
    data["session_uid"] = str(data["session_uid"])
    data["user_uid"]    = str(data["user_uid"])
    return data


# ============================================================
# FINDINGS
# ============================================================

async def save_finding(
    pool:         asyncpg.Pool,
    session_id:   str,
    finding_data: dict,
) -> str:
    """
    Insert finding entity + session_finding link row.
    Wiebe: link table pattern — equipment_part.
    UUIDs from application.
    """
    finding_uid = new_uid()
    session_uid = session_db_uid(session_id)

    await pool.execute(
        """
        INSERT INTO finding
            (finding_uid, description, sludge_type, severity,
             recommended_action, rationale, confidence_score,
             cross_cutting, estimated_burden, affected_domains, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'pending_review')
        """,
        finding_uid,
        finding_data.get("title", ""),
        finding_data.get("sludge_type"),
        finding_data.get("severity"),
        finding_data.get("recommended_action"),
        finding_data.get("rationale"),
        float(finding_data.get("confidence_score", 0.0)),
        bool(finding_data.get("cross_cutting", False)),
        finding_data.get("estimated_burden", ""),
        # jsonb codec on the pool encodes Python lists/dicts directly
        finding_data.get("affected_domains", []),
    )

    # Link row — Wiebe: explicit link table
    await pool.execute(
        "INSERT INTO session_finding (session_uid, finding_uid) VALUES ($1, $2)",
        session_uid, finding_uid,
    )

    for citation in finding_data.get("source_provisions", []):
        await _save_provision_link(pool, finding_uid, citation, "source")

    for citation in finding_data.get("overlapping_provisions", []):
        await _save_provision_link(pool, finding_uid, citation, "overlapping")

    return finding_uid


async def _save_provision_link(
    pool:              asyncpg.Pool,
    finding_uid:       str,
    citation,
    relationship_type: str,
) -> None:
    """
    Insert provision entity + finding_provision link.
    Wiebe: 'one part to many... link table'

    citation: Citation dict {document_title, source_reference,
    verbatim_quote, chunk_uid} or a plain string (legacy).
    The chunk_uid is resolved to the source document_uid so every
    provision row is pinned to the document it came from.
    """
    if isinstance(citation, dict):
        quote     = citation.get("verbatim_quote", "")
        title     = citation.get("document_title", "")
        ref       = citation.get("source_reference", "")
        chunk_uid = _uuid_or_none(citation.get("chunk_uid", ""))
        reference = " — ".join(p for p in (title, ref) if p) or quote[:500]
    else:
        quote, reference, chunk_uid = str(citation), str(citation)[:500], None

    document_uid = None
    if chunk_uid:
        document_uid = await pool.fetchval(
            "SELECT document_uid FROM document_chunk WHERE chunk_uid = $1",
            chunk_uid,
        )

    provision_uid = new_uid()
    await pool.execute(
        """
        INSERT INTO provision
            (provision_uid, description, document_uid, reference_text, status)
        VALUES ($1, $2, $3, $4, 'active')
        """,
        provision_uid, quote, document_uid, reference[:500],
    )
    await pool.execute(
        """
        INSERT INTO finding_provision
            (finding_uid, provision_uid, relationship_type)
        VALUES ($1, $2, $3)
        """,
        finding_uid, provision_uid, relationship_type,
    )


async def update_finding_status(
    pool:         asyncpg.Pool,
    finding_uid:  str,
    status:       str,
    user_uid:     str,
    session_id:   str,
    notes:        str = "",
) -> None:
    """
    Update entity table AND write to finding_log.
    Wiebe: 'I want the status immediately AND the log for history.
            Two operations — done in application, not a trigger.'
    """
    status_from = await pool.fetchval(
        "SELECT status FROM finding WHERE finding_uid = $1", finding_uid
    ) or ""

    await pool.execute(
        "UPDATE finding SET status = $2 WHERE finding_uid = $1",
        finding_uid, status,
    )

    await pool.execute(
        """
        INSERT INTO finding_log
            (log_uid, finding_uid, session_uid, user_uid,
             description, status_from, status_to, log_type)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        new_uid(), finding_uid, session_db_uid(session_id),
        _uuid_or_none(user_uid),
        notes or f"Status -> {status}", status_from, status, status,
    )


async def get_session_findings(pool: asyncpg.Pool, session_id: str) -> List[dict]:
    """
    Get all findings for a session via link table.
    Aliasing 'description' as 'title' per Wiebe's SELECT pattern.
    """
    session_uid = session_db_uid(session_id)

    finding_rows = await pool.fetch(
        """
        SELECT f.finding_uid, f.description AS title, f.sludge_type,
               f.severity, f.recommended_action, f.rationale,
               f.confidence_score, f.cross_cutting, f.estimated_burden,
               f.affected_domains, f.status
        FROM session_finding sf
        JOIN finding f ON f.finding_uid = sf.finding_uid
        WHERE sf.session_uid = $1
        """,
        session_uid,
    )
    if not finding_rows:
        return []

    findings = []
    for row in finding_rows:
        f = dict(row)
        f["finding_uid"] = str(f["finding_uid"])

        prov_rows = await pool.fetch(
            """
            SELECT p.reference_text, fp.relationship_type
            FROM finding_provision fp
            JOIN provision p ON p.provision_uid = fp.provision_uid
            WHERE fp.finding_uid = $1
            """,
            f["finding_uid"],
        )
        f["source_provisions"]      = []
        f["overlapping_provisions"] = []
        for p in prov_rows:
            if p["relationship_type"] == "source":
                f["source_provisions"].append(p["reference_text"])
            else:
                f["overlapping_provisions"].append(p["reference_text"])

        findings.append(f)

    return findings


# ============================================================
# AUDIT LOG
# ============================================================

async def write_audit_log(
    pool:            asyncpg.Pool,
    session_id:      str,
    description:     str,
    log_type:        str,
    status_from:     str = "",
    status_to:       str = "",
    user_uid:        str = "",
    iteration_count: int = 0,
) -> None:
    await pool.execute(
        """
        INSERT INTO audit_log
            (log_uid, session_uid, user_uid, description,
             log_type, status_from, status_to, iteration_count)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        new_uid(), session_db_uid(session_id), _uuid_or_none(user_uid),
        description, log_type, status_from, status_to, iteration_count,
    )
