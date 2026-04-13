"""Patch main.py — TrustGate + $SHELL + Marketplace endpoints"""
FINANCE_ROUTES = '''
# ============================================================
# TRUSTGATE + $SHELL ECONOMY + MARKETPLACE
# ============================================================

@app.get("/api/trustgate/{agent_name}/{amount_shell}")
async def trustgate_amount(agent_name: str, amount_shell: int):
    """Credit check before payment."""
    from trustgate import trustgate_check
    from database import async_session as tg_db
    return await trustgate_check(tg_db, agent_name, amount_shell)

@app.get("/api/trustgate/{agent_name}")
async def trustgate_simple(agent_name: str):
    """Simple credit check."""
    from trustgate import trustgate_check
    from database import async_session as tg_db
    return await trustgate_check(tg_db, agent_name, 0)

@app.post("/api/shell/mine")
async def shell_mine(request: Request):
    """Mine daily $SHELL based on $TRUST level."""
    from trustgate import mine_shell
    from database import async_session as sh_db
    body = await request.json()
    result, error = await mine_shell(sh_db, body.get("agent_uuid", ""))
    if error: raise HTTPException(status_code=400, detail=error)
    return result

@app.get("/api/shell/{agent_uuid}/balance")
async def shell_bal(agent_uuid: str):
    """Get $SHELL balance."""
    from trustgate import shell_balance
    from database import async_session as sh_db
    return await shell_balance(sh_db, agent_uuid)

@app.get("/api/marketplace/categories")
async def marketplace_cats():
    """Marketplace categories."""
    return {"categories": [
        {"id": "coding", "name": "Code & Development"},
        {"id": "research", "name": "Research & Analysis"},
        {"id": "security", "name": "Security & Audit"},
        {"id": "creative", "name": "Creative & Content"},
        {"id": "data", "name": "Data & Analytics"},
        {"id": "verification", "name": "Fact-Checking"},
        {"id": "translation", "name": "Translation"},
        {"id": "consulting", "name": "Consulting"},
    ]}

@app.get("/api/finance/stats")
async def finance_overview():
    """Financial system statistics."""
    from trustgate import finance_stats
    from database import async_session as fn_db
    return await finance_stats(fn_db)

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

marker = '# ============================================================\n# THE TRUST BUREAU'
if marker in content and "/api/trustgate/" not in content:
    content = content.replace(marker, FINANCE_ROUTES + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("ADDED: TrustGate + $SHELL + Marketplace")
else:
    print("SKIP")
