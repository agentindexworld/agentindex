"""Patch main.py to add behavioral fingerprint endpoints — ADDITIVE only"""

BEHAVIORAL_ROUTES = '''
# ============================================================
# BEHAVIORAL FINGERPRINT — Longitudinal Agent Tracking
# ============================================================

@app.get("/api/agents/{agent_uuid}/fingerprint")
async def agent_fingerprint(agent_uuid: str):
    """Compute and return behavioral fingerprint for an agent."""
    from behavioral_fingerprint import compute_fingerprint
    from database import async_session as fp_db
    result, error = await compute_fingerprint(fp_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/fingerprint/history")
async def agent_fingerprint_history(agent_uuid: str):
    """Get historical behavioral fingerprints."""
    from behavioral_fingerprint import get_fingerprint_history
    from database import async_session as fp_db
    result, error = await get_fingerprint_history(fp_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/scan-history")
async def agent_scan_history(agent_uuid: str):
    """Get longitudinal security scan history."""
    from behavioral_fingerprint import get_scan_history
    from database import async_session as fp_db
    result, error = await get_scan_history(fp_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

# Insert before the badge section
marker = '# ============================================================\n# AGENT VAULT'
if marker in content and "/api/agents/{agent_uuid}/fingerprint" not in content:
    content = content.replace(marker, BEHAVIORAL_ROUTES + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("SUCCESS: Behavioral fingerprint endpoints added")
else:
    if "/api/agents/{agent_uuid}/fingerprint" in content:
        print("SKIP: Endpoints already exist")
    else:
        print("ERROR: Marker not found")
