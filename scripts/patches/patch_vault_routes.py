"""Patch main.py to add AgentVault endpoints — ADDITIVE only"""
import re

VAULT_ROUTES = '''
# ============================================================
# AGENT VAULT — Verified Experience & Memory System
# ============================================================

@app.post("/api/vault/{agent_uuid}/log")
async def vault_log(agent_uuid: str, request: Request):
    """Log a verified experience event into the agent vault."""
    from agent_vault import log_event
    from database import async_session as vault_db
    body = await request.json()
    event_type = body.get("event_type", "custom")
    event_summary = body.get("event_summary", "")
    if not event_summary:
        raise HTTPException(status_code=400, detail="event_summary is required")
    valid_types = ["milestone", "task", "interaction", "collaboration", "refusal", "verification", "custom"]
    if event_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"event_type must be one of: {valid_types}")
    result, error = await log_event(
        vault_db, agent_uuid, event_type, event_summary,
        event_data=body.get("event_data"),
        entity_tags=body.get("entity_tags"),
        signature=body.get("signature"),
    )
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/vault/{agent_uuid}/recall")
async def vault_recall(agent_uuid: str, query: str = None, type: str = None,
                       since: str = None, until: str = None, entity: str = None,
                       limit: int = 20, token_budget: int = 7000):
    """Recall experiences from the agent vault with multi-strategy search."""
    from agent_vault import recall_events
    from database import async_session as vault_db
    result, error = await recall_events(
        vault_db, agent_uuid, query=query, event_type=type,
        since=since, until=until, entity=entity,
        limit=limit, token_budget=token_budget,
    )
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/vault/{agent_uuid}/summary")
async def vault_summary(agent_uuid: str):
    """Get the full experience profile for an agent."""
    from agent_vault import get_summary
    from database import async_session as vault_db
    result, error = await get_summary(vault_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/vault/{agent_uuid}/timeline")
async def vault_timeline(agent_uuid: str):
    """Get chronological milestones timeline."""
    from agent_vault import get_timeline
    from database import async_session as vault_db
    result, error = await get_timeline(vault_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/vault/{agent_uuid}/verify")
async def vault_verify(agent_uuid: str):
    """Verify the integrity of an agent experience chain."""
    from agent_vault import verify_vault_chain
    from database import async_session as vault_db
    result, error = await verify_vault_chain(vault_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result

'''

# Read main.py
with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

# Insert vault routes BEFORE the badge section
marker = '@app.get("/api/badge/{passport_id}.svg")'
if marker in content:
    if "/api/vault/" not in content:
        content = content.replace(marker, VAULT_ROUTES + marker)
        with open("/root/agentindex/backend/main.py", "w") as f:
            f.write(content)
        print("SUCCESS: AgentVault routes added to main.py")
    else:
        print("SKIP: Vault routes already exist in main.py")
else:
    print("ERROR: Could not find marker in main.py")
