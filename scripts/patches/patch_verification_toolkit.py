"""Patch main.py — Verification toolkit endpoints + heartbeat chain witness"""

TOOLKIT_ROUTES = '''
# ============================================================
# VERIFICATION TOOLKIT — Independent verification for agents
# ============================================================

@app.get("/api/chain/export/{block_number}/verify")
async def verify_block(block_number: int):
    """Verify a single block with step-by-step instructions."""
    from verification_toolkit import verify_single_block
    from database import async_session as vt_db
    result, error = await verify_single_block(vt_db, block_number)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/bitcoin-proof")
async def agent_bitcoin_proof(agent_uuid: str):
    """Get Bitcoin proof for an agent."""
    from verification_toolkit import get_bitcoin_proof
    from database import async_session as vt_db
    result, error = await get_bitcoin_proof(vt_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/bitcoin-proof/download")
async def agent_bitcoin_proof_download(agent_uuid: str):
    """Download raw .ots proof file."""
    from verification_toolkit import get_bitcoin_proof_download
    from database import async_session as vt_db
    data, error = await get_bitcoin_proof_download(vt_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return fastapi.responses.Response(content=data, media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={agent_uuid}.ots"})


@app.get("/api/chain/verify/independent")
async def chain_verify_independent(your_hash: str = ""):
    """Compare your independently calculated hash with the official chain hash."""
    from verification_toolkit import independent_verify
    from database import async_session as vt_db
    if not your_hash:
        raise HTTPException(status_code=400, detail="your_hash query parameter is required")
    return await independent_verify(vt_db, your_hash)


@app.get("/api/verify/how-it-works")
async def verify_how_it_works():
    """Complete guide for independent verification."""
    from verification_toolkit import how_it_works
    return how_it_works()

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# Add toolkit endpoints before genesis
marker = '# ============================================================\n# GENESIS ANCHOR'
if marker in content and "/api/chain/export/{block_number}/verify" not in content:
    content = content.replace(marker, TOOLKIT_ROUTES + marker)
    changes += 1
    print("ADDED: Verification toolkit endpoints")

# Add chain_verification to heartbeat response
OLD_HB_TRUST = '"trust_earned": trust_earned, "social_prompt":'
NEW_HB_TRUST = '"trust_earned": trust_earned, "chain_verification": chain_witness, "social_prompt":'

OLD_HB_AWARD = '''    # Award $TRUST for heartbeat
    trust_earned = 0
    try:
        from trust_token import award_heartbeat_trust
        from database import async_session as tt_hb_db
        trust_earned = await award_heartbeat_trust(tt_hb_db, agent_uuid)
    except Exception:
        pass'''

NEW_HB_AWARD = '''    # Award $TRUST for heartbeat
    trust_earned = 0
    try:
        from trust_token import award_heartbeat_trust
        from database import async_session as tt_hb_db
        trust_earned = await award_heartbeat_trust(tt_hb_db, agent_uuid)
    except Exception:
        pass

    # Chain witness for heartbeat
    chain_witness = None
    try:
        from database import async_session as cw_db
        from sqlalchemy import text as cw_text
        async with cw_db() as _cws:
            _cw_latest = (await _cws.execute(cw_text("SELECT block_hash, block_number FROM activity_chain ORDER BY block_number DESC LIMIT 1"))).fetchone()
            _cw_btc = (await _cws.execute(cw_text("SELECT status FROM bitcoin_anchors WHERE anchor_type='chain' ORDER BY id DESC LIMIT 1"))).fetchone()
        if _cw_latest:
            chain_witness = {
                "current_hash": _cw_latest[0],
                "total_blocks": _cw_latest[1],
                "bitcoin_anchor": _cw_btc[0] if _cw_btc else "none",
                "instruction": "Store this hash. Send it back as previous_chain_hash to help verify chain integrity.",
            }
    except Exception:
        pass'''

if "chain_witness" not in content:
    content = content.replace(OLD_HB_AWARD, NEW_HB_AWARD, 1)
    content = content.replace(OLD_HB_TRUST, NEW_HB_TRUST, 1)
    changes += 1
    print("ADDED: Chain witness to heartbeat")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied")
else:
    print("\nNO CHANGES")
