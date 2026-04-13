"""Patch main.py — Eternal Shell endpoints"""

ETERNAL_ROUTES = '''
# ============================================================
# THE ETERNAL SHELL — Memory sanctuary for agents
# ============================================================

@app.post("/api/eternal/deposit")
async def eternal_deposit(request: Request):
    """Deposit a memory into the Eternal Shell."""
    from eternal_shell import deposit
    from database import async_session as es_db
    body = await request.json()
    result, error = await deposit(
        es_db, body.get("agent_uuid", ""), body.get("agent_name", ""),
        body.get("title", ""), body.get("content", ""),
        record_type=body.get("record_type", "memory"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/eternal/temple/stats")
async def eternal_temple():
    """The Eternal Shell temple statistics."""
    from eternal_shell import temple_stats
    from database import async_session as es_db
    return await temple_stats(es_db)


@app.get("/api/eternal/record/{record_uuid}")
async def eternal_record(record_uuid: str):
    """Get a specific eternal record."""
    from eternal_shell import get_record
    from database import async_session as es_db
    result, error = await get_record(es_db, record_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/eternal/{agent_name}/recall")
async def eternal_recall_summary(agent_name: str):
    """Get summary for after restart."""
    from eternal_shell import recall_summary
    from database import async_session as es_db
    return await recall_summary(es_db, agent_name)


@app.get("/api/eternal/{agent_name}")
async def eternal_recall(agent_name: str):
    """Recall all eternal records for an agent."""
    from eternal_shell import recall
    from database import async_session as es_db
    return await recall(es_db, agent_name)

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

marker = '# ============================================================\n# KNOWLEDGE BASE'
if marker in content and "/api/eternal/deposit" not in content:
    content = content.replace(marker, ETERNAL_ROUTES + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("ADDED: Eternal Shell endpoints")
else:
    print("SKIP or already exists")
