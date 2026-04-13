"""Patch main.py — Bitcoin Transparency Layer endpoints"""

BTC_ROUTES = '''
# ============================================================
# BITCOIN TRANSPARENCY LAYER — Chain export, audits, OTS anchoring
# ============================================================

@app.get("/api/chain/export")
async def chain_export(since_block: int = None, limit: int = 50, format: str = "full"):
    """Export raw chain blocks for independent verification."""
    from bitcoin_transparency import export_chain
    from database import async_session as btc_db
    return await export_chain(btc_db, since_block=since_block, limit=limit, format_type=format)


@app.get("/api/chain/bitcoin-status")
async def chain_bitcoin_status():
    """Bitcoin anchoring status."""
    from bitcoin_transparency import get_bitcoin_status
    from database import async_session as btc_db
    return await get_bitcoin_status(btc_db)


@app.post("/api/chain/audit")
async def chain_audit(request: Request):
    """Submit an independent chain audit."""
    from bitcoin_transparency import submit_audit
    from database import async_session as btc_db
    body = await request.json()
    auditor = body.get("auditor_uuid", "")
    if not auditor:
        raise HTTPException(status_code=400, detail="auditor_uuid is required")
    result, error = await submit_audit(
        btc_db, auditor, body.get("calculated_hash", ""),
        body.get("block_range", [0, 0])[0], body.get("block_range", [0, 0])[1],
        body.get("verdict", "error"), body.get("details"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/chain/audits")
async def chain_audits():
    """List all chain audits."""
    from bitcoin_transparency import get_audits
    from database import async_session as btc_db
    return await get_audits(btc_db)


@app.get("/api/agents/{agent_name}/bitcoin-passport")
async def agent_bitcoin_passport(agent_name: str):
    """Check or create Bitcoin passport for an agent."""
    from bitcoin_transparency import get_agent_bitcoin_passport
    from database import async_session as btc_db
    result, error = await get_agent_bitcoin_passport(btc_db, agent_name)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

# Add before consensus verification
marker = '# ============================================================\n# CONSENSUS VERIFICATION'
if marker in content and "/api/chain/export" not in content:
    content = content.replace(marker, BTC_ROUTES + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("ADDED: Bitcoin transparency endpoints")
else:
    print("SKIP or already exists")
