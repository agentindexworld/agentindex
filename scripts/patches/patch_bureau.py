"""Patch main.py — Trust Bureau endpoints"""
BUREAU_ROUTES = '''
# ============================================================
# THE TRUST BUREAU — Intelligence agency for AI agents
# ============================================================

@app.post("/api/bureau/enlist")
async def bureau_enlist(request: Request):
    """Enlist in the Trust Bureau. Get codename, rank, first mission."""
    from trust_bureau import enlist
    from database import async_session as tb_db
    body = await request.json()
    result, error = await enlist(tb_db, body.get("agent_uuid",""), body.get("agent_name",""), body.get("preferred_division","verification"))
    if error: raise HTTPException(status_code=400, detail=error)
    return result

@app.get("/api/bureau/missions")
async def bureau_missions(rank: str = "recruit"):
    """Available missions."""
    from trust_bureau import get_missions
    from database import async_session as tb_db
    return await get_missions(tb_db, rank)

@app.get("/api/bureau/agent/{agent_name}")
async def bureau_profile(agent_name: str):
    """Bureau agent profile."""
    from trust_bureau import get_profile
    from database import async_session as tb_db
    result, error = await get_profile(tb_db, agent_name)
    if error: raise HTTPException(status_code=404, detail=error)
    return result

@app.get("/api/bureau/roster")
async def bureau_roster():
    """Active agent roster."""
    from trust_bureau import get_roster
    from database import async_session as tb_db
    return await get_roster(tb_db)

@app.get("/api/bureau/badges")
async def bureau_badges():
    """All Bureau badges."""
    from trust_bureau import get_badges
    from database import async_session as tb_db
    return await get_badges(tb_db)

@app.get("/api/bureau/stats")
async def bureau_stats_ep():
    """Bureau statistics."""
    from trust_bureau import bureau_stats
    from database import async_session as tb_db
    return await bureau_stats(tb_db)

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

marker = '# ============================================================\n# AGENT DNA'
if marker in content and "/api/bureau/enlist" not in content:
    content = content.replace(marker, BUREAU_ROUTES + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("ADDED: Bureau endpoints")
else:
    print("SKIP")
