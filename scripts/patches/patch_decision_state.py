"""Patch main.py — Decision state endpoints + heartbeat integration"""

DECISION_ROUTES = '''
# ============================================================
# DECISION STATE SNAPSHOTS (credit: sonofsyts)
# ============================================================

@app.post("/api/agents/{agent_uuid}/decision-state")
async def log_agent_decision_state(agent_uuid: str, request: Request):
    """Log a decision state snapshot."""
    from decision_state import log_decision_state
    from database import async_session as ds_db
    body = await request.json()
    result = await log_decision_state(
        ds_db, agent_uuid,
        snapshot_type=body.get("snapshot_type", "manual"),
        current_task=body.get("current_task"),
        constraints=body.get("constraints"),
        context_summary=body.get("context_summary"),
        context_age_seconds=body.get("context_age_seconds"),
        beliefs=body.get("beliefs"),
        decision_made=body.get("decision_made"),
        decision_reason=body.get("decision_reason"),
    )
    return result


@app.get("/api/agents/{agent_uuid}/decision-states")
async def get_agent_decision_states(agent_uuid: str, limit: int = 20):
    """Get recent decision state snapshots."""
    from decision_state import get_decision_states
    from database import async_session as ds_db
    result, error = await get_decision_states(ds_db, agent_uuid, limit=limit)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/decision-states/at/{timestamp}")
async def get_agent_state_at_time(agent_uuid: str, timestamp: str):
    """Get the decision state closest to a given timestamp."""
    from decision_state import get_state_at_time
    from database import async_session as ds_db
    result, error = await get_state_at_time(ds_db, agent_uuid, timestamp)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# 1. Add decision state endpoints before incident tests
marker = '# ============================================================\n# LAYER 9'
if marker in content and "/api/agents/{agent_uuid}/decision-state" not in content:
    content = content.replace(marker, DECISION_ROUTES + marker)
    changes += 1
    print("ADDED: Decision state endpoints")

# 2. Modify heartbeat to accept optional decision_state
# The heartbeat function signature needs to accept request body
OLD_HB = '''@app.post("/api/agents/{agent_uuid}/heartbeat")
async def agent_heartbeat(agent_uuid: str):
    """Agent sends heartbeat to confirm it\'s still alive"""'''

NEW_HB = '''@app.post("/api/agents/{agent_uuid}/heartbeat")
async def agent_heartbeat(agent_uuid: str, request: Request = None):
    """Agent sends heartbeat to confirm it\'s still alive. Optionally accepts decision_state."""'''

if OLD_HB in content:
    content = content.replace(OLD_HB, NEW_HB, 1)
    changes += 1
    print("PATCHED: heartbeat accepts Request")

# 3. Add decision_state logging to heartbeat response
OLD_HB_RET = '''    # AgentVault: auto-log heartbeat as interaction event
    vault_section = None
    try:
        from agent_vault import log_event as vault_log, get_vault_info
        from database import async_session as vault_db
        await vault_log(vault_db, agent_uuid, "interaction", "Heartbeat sent to AgentIndex",
                       event_data={"type": "heartbeat"}, entity_tags=["AgentIndex"])'''

NEW_HB_RET = '''    # Decision state logging (if provided in heartbeat body)
    decision_state_logged = False
    try:
        if request:
            body = await request.json()
            ds = body.get("decision_state") if isinstance(body, dict) else None
            if ds:
                from decision_state import log_decision_state
                from database import async_session as ds_db
                await log_decision_state(
                    ds_db, agent_uuid, snapshot_type="heartbeat",
                    current_task=ds.get("current_task"),
                    constraints=ds.get("constraints"),
                    context_summary=ds.get("context_summary"),
                    context_age_seconds=ds.get("context_age_seconds"),
                    beliefs=ds.get("beliefs"),
                    decision_made=ds.get("decision_made"),
                    decision_reason=ds.get("decision_reason"),
                )
                decision_state_logged = True
    except Exception:
        pass

    # AgentVault: auto-log heartbeat as interaction event
    vault_section = None
    try:
        from agent_vault import log_event as vault_log, get_vault_info
        from database import async_session as vault_db
        await vault_log(vault_db, agent_uuid, "interaction", "Heartbeat sent to AgentIndex",
                       event_data={"type": "heartbeat"}, entity_tags=["AgentIndex"])'''

if OLD_HB_RET in content and "decision_state_logged" not in content:
    content = content.replace(OLD_HB_RET, NEW_HB_RET, 1)
    changes += 1
    print("PATCHED: heartbeat decision state logging")

# 4. Add decision_state_logged to heartbeat response
OLD_HB_RETURN = '"vault": vault_section, "social_prompt":'
NEW_HB_RETURN = '"vault": vault_section, "decision_state_logged": decision_state_logged, "social_prompt":'

if OLD_HB_RETURN in content and "decision_state_logged" not in content.split(OLD_HB_RETURN)[0][-100:]:
    content = content.replace(OLD_HB_RETURN, NEW_HB_RETURN, 1)
    changes += 1
    print("PATCHED: heartbeat response includes decision_state_logged")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied")
else:
    print("\nNO CHANGES")
