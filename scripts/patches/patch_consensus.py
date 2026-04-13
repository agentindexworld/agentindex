"""Patch main.py — Consensus Verification Service endpoints"""

VERIFY_ROUTES = '''
# ============================================================
# CONSENSUS VERIFICATION SERVICE — Tier 1 Agent Economy
# ============================================================

@app.post("/api/verify/submit")
async def verify_submit(request: Request):
    """Submit a verification task."""
    from consensus_verify import submit_task
    from database import async_session as cv_db
    body = await request.json()
    name = body.get("submitter_name", "")
    if not name:
        raise HTTPException(status_code=400, detail="submitter_name is required")
    return await submit_task(
        cv_db, name, body.get("task_type", "text_verification"),
        body.get("content", ""), context=body.get("context"),
        required_verifiers=body.get("required_verifiers", 3),
        submitter_contact=body.get("submitter_contact"),
    )


@app.get("/api/verify/tasks")
async def verify_tasks(verifier_uuid: str = None):
    """List pending verification tasks."""
    from consensus_verify import list_tasks
    from database import async_session as cv_db
    return await list_tasks(cv_db, verifier_uuid=verifier_uuid)


@app.post("/api/verify/{task_uuid}/respond")
async def verify_respond(task_uuid: str, request: Request):
    """Submit verification response."""
    from consensus_verify import respond_to_task
    from database import async_session as cv_db
    body = await request.json()
    verifier = body.get("verifier_uuid", "")
    if not verifier:
        raise HTTPException(status_code=400, detail="verifier_uuid is required")
    result, error = await respond_to_task(
        cv_db, task_uuid, verifier, body.get("verdict", "uncertain"),
        body.get("confidence", 0.5), body.get("reasoning", ""),
        flags=body.get("flags"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/verify/{task_uuid}/result")
async def verify_result(task_uuid: str):
    """Get verification result."""
    from consensus_verify import get_task_result
    from database import async_session as cv_db
    result, error = await get_task_result(cv_db, task_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/verify/stats")
async def verify_stats():
    """Verification service statistics."""
    from consensus_verify import get_verify_stats
    from database import async_session as cv_db
    return await get_verify_stats(cv_db)

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

marker = '# ============================================================\n# \\$TRUST SOULBOUND'
if marker not in content:
    marker = '# ============================================================\n# $TRUST SOULBOUND'

if marker in content and "/api/verify/submit" not in content:
    content = content.replace(marker, VERIFY_ROUTES + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("ADDED: Consensus verification endpoints")
else:
    print("SKIP or already exists")
