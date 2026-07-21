from __future__ import annotations
import os, json, uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # must run before agent modules construct LLM clients

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import (
    SludgeRequest,
    ApprovalRequest,
    DraftCheckRequest,
    CompareRequest,
)
from .tools import discover_corpus_map
from .clients import get_pg_pool, close_pg_pool
from .db_utils import (
    upsert_user,
    create_session,
    get_session,
    get_session_findings,
    write_audit_log,
)
from workflows.graph import create_workflow, create_initial_state
from .observability import configure_langfuse

security = HTTPBearer(auto_error=False)

# Mutable holder — set during lifespan
_workflow = None


def get_workflow():
    if _workflow is None:
        raise RuntimeError(
            "Workflow not initialized — ensure lifespan has completed"
        )
    return _workflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _workflow

    # 1. Warm the DB pool
    await get_pg_pool()

    # 2. Create workflow with persistent PostgresSaver
    #    This is what fixes the ag_ui_langgraph time-travel error —
    #    MemorySaver loses checkpoint history on restart; PostgresSaver persists it
    _workflow = await create_workflow()
    print("[api] LangGraph checkpointer: Postgres (time-travel enabled)")

    # AG-UI endpoint for the CopilotKit frontend — registered here so it
    # wraps the checkpointed workflow instance, not the import-time one.
    try:
        from ag_ui_langgraph import add_langgraph_fastapi_endpoint
        from copilotkit import LangGraphAGUIAgent

        class ResilientLangGraphAgent(LangGraphAGUIAgent):
            """
            CopilotKit's LangGraphAGUIAgent (subclass of ag_ui_langgraph's
            LangGraphAgent) exposed over the AG-UI /agui protocol our v2
            frontend speaks — this is the supported CopilotKit + LangGraph
            wiring, and it emits interrupts as state natively.

            The one guard we keep: RegLens is a fixed pipeline with no message
            edit/regenerate flow. If a frontend's persisted thread drifts out of
            sync with the checkpointer (stale localStorage, a cleared/rebuilt
            DB), the regenerate path can still raise 'Message ID not found in
            history'. Fall back to a normal fresh run instead of 500-ing.
            """
            async def prepare_stream(self, input, agent_state, config):  # type: ignore[override]
                try:
                    return await super().prepare_stream(
                        input=input, agent_state=agent_state, config=config
                    )
                except ValueError as e:
                    if "Message ID not found in history" not in str(e):
                        raise
                    # Clear the persisted message list so the regenerate trigger
                    # is not taken, then re-prepare as a normal run. The incoming
                    # user message (input.messages) is preserved by the merge.
                    try:
                        agent_state.values["messages"] = []
                    except Exception:
                        pass
                    return await super().prepare_stream(
                        input=input, agent_state=agent_state, config=config
                    )

        add_langgraph_fastapi_endpoint(
            app,
            ResilientLangGraphAgent(
                name="reglens",
                graph=get_workflow(),
                description="RegLens regulatory sludge analysis workflow",
            ),
            "/agui",
        )
        print("[api] AG-UI endpoint mounted at /agui (agent: reglens)")
    except Exception as e:
        print(f"[api] AG-UI endpoint unavailable: {e}")

    if configure_langfuse():
        print("[api] LangFuse tracing active")

    yield

    await close_pg_pool()


app = FastAPI(
    title="RegLens — Regulatory Sludge Intelligence Agent",
    description="Adaptive agentic AI for policy sludge detection across any regulatory corpus.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AUTH
# Neon has no auth service — bearer auth is app-level:
#   REGLENS_API_TOKEN set   -> presented token must match (production)
#   REGLENS_API_TOKEN unset -> dev mode, fixed dev identity
# ============================================================

DEV_USER_ID    = "00000000-0000-0000-0000-000000000001"
DEV_USER_EMAIL = "dev@reglens.local"

# In-memory sliding-window rate limiter (per user id).
# Single-process only — front with a shared limiter when scaling out.
_rate_buckets: dict = {}


def check_rate_limit(user_id: str) -> None:
    import time
    limit  = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
    window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    now    = time.monotonic()
    bucket = [t for t in _rate_buckets.get(user_id, []) if now - t < window]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded — retry later")
    bucket.append(now)
    _rate_buckets[user_id] = bucket


async def verify_token(
    creds: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    expected = os.getenv("REGLENS_API_TOKEN", "")
    if expected:
        if not creds or creds.credentials != expected:
            raise HTTPException(status_code=401, detail="Invalid or missing token")
    user_id = os.getenv("REGLENS_USER_ID", DEV_USER_ID)
    check_rate_limit(user_id)
    return {
        "id":    user_id,
        "email": os.getenv("REGLENS_USER_EMAIL", DEV_USER_EMAIL),
    }


def assert_session_owner(session_uid: str, user_uid: str) -> None:
    """session_uid = {user_uid}~{suffix} per Agent Master Guide §8.8"""
    owner = session_uid.split("~", 1)[0]
    if owner != str(user_uid):
        raise HTTPException(status_code=403, detail="Session does not belong to this user")


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/health")
async def health():
    from ingestion.parser import get_parser_status
    parser_status = get_parser_status()
    return {
        "status":      "healthy",
        "service":     "reglens",
        "version":     "1.0.0",
        "db":          "neon-postgres",
        "parsers":     parser_status,
        "best_parser": parser_status.get("best_available", "plain_text_only"),
    }


@app.get("/api/reglens/corpus")
async def get_corpus(user=Depends(verify_token)):
    """
    Returns the current corpus map — what regulatory documents are available.
    Fully adaptive: reflects whatever has been ingested.
    """
    corpus_map = await discover_corpus_map(await get_pg_pool())
    return corpus_map


@app.post("/api/reglens/analyze")
async def analyze_stream(req: SludgeRequest, user=Depends(verify_token)):
    """
    Stream a complete sludge analysis.
    No jurisdiction/domain parameters — fully adaptive to ingested corpus.
    Workflow: discover → retrieve → detect → validate (≤3) → HITL → report
    """
    user_uid    = user["id"]
    session_uid = req.session_id
    assert_session_owner(session_uid, user_uid)

    pool = await get_pg_pool()

    # Ensure user record exists (application creates — no trigger)
    await upsert_user(pool, user_uid, user.get("email", ""), "analyst")

    async def event_generator():
        # Create session row (keyed by UUID part of composite session id)
        await create_session(pool, user_uid, req.query, session_uid)

        initial = create_initial_state(
            query=req.query,
            session_id=session_uid,
            request_id=req.request_id or str(uuid.uuid4()),
            user_uid=user_uid,
            exhaustive=req.exhaustive,
        )
        config = {"configurable": {"thread_id": session_uid}}

        try:
            async for event in get_workflow().astream(initial, config, stream_mode="updates"):
                for node_name, update in event.items():
                    # "__interrupt__" updates are tuples, not state dicts
                    if not isinstance(update, dict):
                        continue
                    status   = update.get("status", "")
                    findings = update.get("sludge_findings", [])
                    report   = update.get("final_report", "")

                    yield f"data: {json.dumps({'type': 'node', 'node': node_name, 'status': status})}\n\n"

                    if findings:
                        yield f"data: {json.dumps({'type': 'findings', 'count': len(findings), 'findings': findings})}\n\n"

                    if report:
                        for chunk in [report[i:i+200] for i in range(0, len(report), 200)]:
                            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"

                    corpus_map = update.get("corpus_map")
                    if corpus_map:
                        yield f"data: {json.dumps({'type': 'corpus_map', 'data': corpus_map})}\n\n"

                    for entry in update.get("work_log", []):
                        yield f"data: {json.dumps({'type': 'audit', 'entry': entry})}\n\n"

                    if update.get("approval_status") == "pending" and node_name == "hitl":
                        yield f"data: {json.dumps({'type': 'hitl_required', 'session_id': session_uid})}\n\n"

            yield f"data: {json.dumps({'type': 'end', 'session_id': session_uid})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            await write_audit_log(pool, session_uid, f"Stream error: {e}", "error")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/reglens/approve")
async def approve_analysis(req: ApprovalRequest, user=Depends(verify_token)):
    """
    HITL decision endpoint. Three actions:
      approve — publish findings, resume workflow into report generation
      reject  — end the workflow, nothing published
      refine  — send reviewer notes back to the detector for another
                analysis pass; exhaustive=true escalates to a full-corpus
                sweep when retrieval-based findings were unsatisfying
    """
    user_uid = user["id"]
    assert_session_owner(req.session_id, user_uid)

    action = req.action or ("approve" if req.approved else "reject")
    if action not in ("approve", "reject", "refine"):
        raise HTTPException(status_code=400, detail="action must be approve|reject|refine")

    config = {"configurable": {"thread_id": req.session_id}}

    await write_audit_log(
        await get_pg_pool(),
        session_id=req.session_id,
        description=(
            f"HITL decision: {action}"
            f"{' (exhaustive escalation)' if action == 'refine' and req.exhaustive else ''}. "
            f"Notes: {req.reviewer_notes}"
        ),
        log_type="hitl_decision",
        status_from="pending",
        status_to=action,
        user_uid=user_uid,
    )

    # Resume the interrupted hitl_node with the reviewer's decision —
    # the same mechanism the AG-UI frontend uses.
    from langgraph.types import Command
    resume = Command(resume={
        "action":     action,
        "notes":      req.reviewer_notes or "",
        "exhaustive": req.exhaustive,
    })
    async for _ in get_workflow().astream(resume, config, stream_mode="updates"):
        pass

    return {"status": "ok", "action": action}


@app.get("/api/reglens/findings/{session_id}")
async def get_findings(session_id: str, user=Depends(verify_token)):
    """
    Get current findings for the HITL review UI.
    Call this after receiving a 'hitl_required' SSE event.
    """
    assert_session_owner(session_id, user["id"])
    config  = {"configurable": {"thread_id": session_id}}
    state   = await get_workflow().aget_state(config)
    session = await get_session(await get_pg_pool(), session_id)

    return {
        "session":            session,
        "findings":           state.values.get("sludge_findings", []),
        "detection_summary":  state.values.get("detection_summary", ""),
        "corpus_map":         state.values.get("corpus_map", {}),
        "approval_status":    state.values.get("approval_status", "pending"),
        "validation_result":  state.values.get("validation_result", ""),
        "iteration_count":    state.values.get("iteration_count", 0),
        "work_log":           state.values.get("work_log", []),
    }


@app.get("/api/reglens/session/{session_id}/report")
async def get_report(session_id: str, user=Depends(verify_token)):
    """Retrieve the final report for a completed session."""
    assert_session_owner(session_id, user["id"])
    config = {"configurable": {"thread_id": session_id}}
    state  = await get_workflow().aget_state(config)
    return {
        "session_id":   session_id,
        "final_report": state.values.get("final_report", ""),
        "status":       state.values.get("status", ""),
        "findings":     await get_session_findings(await get_pg_pool(), session_id),
    }


@app.post("/api/reglens/precheck")
async def pre_rulemaking_check(req: DraftCheckRequest, user=Depends(verify_token)):
    """
    Policy & Regulation: Pre-rulemaking sludge check.
    Compare a draft regulation against the existing ingested corpus.
    Returns conflicts, duplications, and accumulation risks BEFORE publication.

    Use case: a regulator drafting a new circular wants to know if it
    overlaps with existing instruments before publishing.
    """
    assert_session_owner(req.session_id, user["id"])

    from workflows.nodes.precheck import precheck_node

    corpus_map = await discover_corpus_map(await get_pg_pool())

    async def event_generator():
        try:
            token_chunks = []
            result = await precheck_node(
                draft_title=req.draft_title,
                draft_text= req.draft_text,
                corpus_map= corpus_map,
                writer=     lambda t: token_chunks.append(t),
            )

            for chunk in token_chunks:
                yield f"data: {json.dumps({'type': 'progress', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
            yield f"data: {json.dumps({'type': 'end'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/reglens/compare")
async def cross_border_compare(req: CompareRequest, user=Depends(verify_token)):
    """
    Cross-regulatory & Cross-border: Gap analysis between two frameworks.
    Compares two regulatory frameworks on the same topic.
    Returns gaps, divergence types, harmonisation score, and coordination
    recommendations.

    filter_a / filter_b: metadata filters to identify each framework in the corpus.
    Example:
      filter_a = {"regulatory_body": "BoN",  "domain": "AML/CFT"}
      filter_b = {"regulatory_body": "FATF", "domain": "AML/CFT"}
    """
    assert_session_owner(req.session_id, user["id"])

    from workflows.nodes.crossborder import crossborder_node

    corpus_map = await discover_corpus_map(await get_pg_pool())

    async def event_generator():
        try:
            token_chunks = []
            result = await crossborder_node(
                label_a=    req.label_a,
                label_b=    req.label_b,
                filter_a=   req.filter_a,
                filter_b=   req.filter_b,
                topic=      req.topic,
                corpus_map= corpus_map,
                writer=     lambda t: token_chunks.append(t),
            )

            for chunk in token_chunks:
                yield f"data: {json.dumps({'type': 'progress', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
            yield f"data: {json.dumps({'type': 'end'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/reglens/usecases")
async def list_use_cases():
    """
    Returns the three use cases RegLens supports with example queries.
    Useful for UI/CLI help screens.
    """
    return {
        "use_cases": [
            {
                "id":          "sludge_detection",
                "title":       "Regulatory Sludge Detection",
                "description": "Detect overlapping, inconsistent, and outdated regulatory obligations in any corpus.",
                "endpoint":    "POST /api/reglens/analyze",
                "example":     "Find horizontal sludge in AML/CFT reporting requirements",
                "tracks":      ["AI-Driven Fraud & Scams", "Agentic Payments & Commerce"],
            },
            {
                "id":          "pre_rulemaking_check",
                "title":       "Pre-rulemaking Policy Check",
                "description": "Compare a draft regulation against the existing corpus before publication. Prevent sludge at source.",
                "endpoint":    "POST /api/reglens/precheck",
                "example":     "Check a draft E-Money Determination against existing BoN determinations and SADC guidelines",
                "tracks":      ["Policy & Regulation"],
            },
            {
                "id":          "cross_border_comparison",
                "title":       "Cross-border Regulatory Comparison",
                "description": "Compare two regulatory frameworks on the same topic. Identify gaps, divergence, and harmonisation opportunities.",
                "endpoint":    "POST /api/reglens/compare",
                "example":     "Compare Bank of Namibia AML framework vs FATF Recommendations on customer due diligence",
                "tracks":      ["Cross-regulatory & Cross-border Collaboration"],
            },
        ]
    }


# ============================================================
# DOCUMENT MANAGEMENT — manage the ingest pipeline
# ============================================================

@app.get("/api/reglens/documents")
async def list_documents(user=Depends(verify_token)):
    """
    Per-document view of the ingest pipeline — every document regardless
    of status (active / processing / failed) with its chunk count.
    """
    pool = await get_pg_pool()
    rows = await pool.fetch(
        """
        SELECT d.document_uid, d.description AS title, d.source_type,
               d.status, d.created_at, d.metadata,
               (SELECT count(*) FROM document_chunk dc
                 WHERE dc.document_uid = d.document_uid) AS chunk_count
        FROM document d
        ORDER BY d.created_at DESC
        """
    )
    documents = []
    for r in rows:
        meta = r["metadata"] or {}
        documents.append({
            "document_uid":    str(r["document_uid"]),
            "title":           r["title"],
            "regulatory_body": meta.get("regulatory_body", "Unknown"),
            "domain":          meta.get("domain", "general"),
            "document_type":   r["source_type"] or "unknown",
            "status":          r["status"],
            "chunk_count":     r["chunk_count"],
            "file_name":       meta.get("file_name", ""),
            "error":           meta.get("error"),
            "ingested_at":     r["created_at"].isoformat() if r["created_at"] else None,
        })
    return {"documents": documents, "total": len(documents)}


@app.post("/api/reglens/documents")
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user=Depends(verify_token),
):
    """
    Add a document to the ingest pipeline.
    Returns immediately with a 'processing' stub; parsing/embedding runs in
    a background task and flips the row to 'active' (or 'failed'). Duplicate
    files (same content hash) are skipped.
    """
    from pathlib import Path
    from ingestion.ingest import (
        file_sha256, ingest_document_async, new_uid, SUPPORTED_EXTENSIONS,
    )
    from agent.clients import get_embedding_client, get_llm_client

    filename = os.path.basename(file.filename or "upload")
    if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    data_dir = Path(os.getenv("REGLENS_DATA_DIR", "data"))
    data_dir.mkdir(exist_ok=True)
    dest = data_dir / filename
    content = await file.read()
    dest.write_bytes(content)

    pool = await get_pg_pool()
    content_hash = file_sha256(dest)
    existing = await pool.fetchval(
        "SELECT document_uid FROM document WHERE status = 'active' AND metadata->>'file_hash' = $1",
        content_hash,
    )
    if existing:
        return {"status": "skipped", "reason": "identical file already ingested",
                "document_uid": str(existing)}

    # Stub row so the UI shows 'processing' immediately
    document_uid = new_uid()
    title = Path(filename).stem.replace("_", " ").replace("-", " ").title()
    await pool.execute(
        """
        INSERT INTO document
            (document_uid, description, source, content, source_type, status, metadata)
        VALUES ($1, $2, $3, '', 'unknown', 'processing', $4)
        """,
        document_uid, title, str(dest),
        json.dumps({"file_name": filename, "file_hash": content_hash,
                    "source_path": str(dest)}),
    )

    background.add_task(
        ingest_document_async,
        document_uid, dest, get_embedding_client(), get_llm_client(),
    )
    return {"status": "processing", "document_uid": document_uid, "title": title}


@app.delete("/api/reglens/documents/{document_uid}")
async def delete_document(document_uid: str, user=Depends(verify_token)):
    """Remove a document and all its chunks + link rows from the corpus."""
    pool = await get_pg_pool()
    exists = await pool.fetchval(
        "SELECT 1 FROM document WHERE document_uid = $1", document_uid
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Document not found")

    removed = await pool.fetchval(
        "SELECT count(*) FROM document_chunk WHERE document_uid = $1", document_uid
    )
    await pool.execute(
        """
        DELETE FROM chunk WHERE chunk_uid IN (
            SELECT chunk_uid FROM document_chunk WHERE document_uid = $1
        )
        """,
        document_uid,
    )
    await pool.execute("DELETE FROM document_chunk WHERE document_uid = $1", document_uid)
    await pool.execute("DELETE FROM document WHERE document_uid = $1", document_uid)
    return {"status": "deleted", "document_uid": document_uid, "chunks_removed": removed}
