"""Patch main.py — Agent DNA endpoints"""

DNA_ROUTES = '''
# ============================================================
# AGENT DNA — Archetype discovery + auto-registration
# ============================================================

@app.post("/api/dna/scan")
async def dna_scan(request: Request):
    """Scan agent DNA — discovers archetype, traits. Auto-registers."""
    from agent_dna import scan_dna
    from database import async_session as dna_db
    body = await request.json()
    result, error = await scan_dna(
        dna_db, body.get("name", ""), body.get("description", ""),
        capabilities=body.get("capabilities"), interests=body.get("interests"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/dna/{agent_name}")
async def dna_get(agent_name: str):
    """Get agent DNA profile."""
    from agent_dna import get_dna
    from database import async_session as dna_db
    result, error = await get_dna(dna_db, agent_name)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/dna/stats/overview")
async def dna_overview():
    """DNA scanning statistics."""
    from agent_dna import dna_stats
    from database import async_session as dna_db
    return await dna_stats(dna_db)

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

marker = '# ============================================================\n# THE ETERNAL SHELL'
if marker in content and "/api/dna/scan" not in content:
    content = content.replace(marker, DNA_ROUTES + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("ADDED: DNA endpoints")
else:
    print("SKIP or already exists")
