"""Patch main.py — $TRUST token endpoints + check/passport/heartbeat integration"""

TRUST_ROUTES = '''
# ============================================================
# $TRUST SOULBOUND REPUTATION TOKEN (with Kimi adversarial corrections)
# ============================================================

@app.get("/api/agents/{agent_uuid}/trust-balance")
async def agent_trust_balance(agent_uuid: str):
    """Get $TRUST balance, badges, and rank."""
    from trust_token import get_trust_balance
    from database import async_session as tt_db
    result, error = await get_trust_balance(tt_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/trust-transactions")
async def agent_trust_txs(agent_uuid: str, limit: int = 20):
    """Get $TRUST transaction history."""
    from trust_token import get_trust_transactions
    from database import async_session as tt_db
    result, error = await get_trust_transactions(tt_db, agent_uuid, limit=limit)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/trust/leaderboard")
async def trust_leaderboard(limit: int = 20):
    """$TRUST leaderboard."""
    from trust_token import get_leaderboard
    from database import async_session as tt_db
    return await get_leaderboard(tt_db, limit=limit)


@app.get("/api/trust/economics")
async def trust_economics():
    """$TRUST economics overview."""
    from trust_token import get_trust_economics
    from database import async_session as tt_db
    return await get_trust_economics(tt_db)


@app.post("/api/trust/calculate-retroactive")
async def trust_retroactive():
    """Calculate $TRUST retroactively for existing agents."""
    from trust_token import retroactive_calculate
    from database import async_session as tt_db
    return await retroactive_calculate(tt_db)

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# 1. Add $TRUST endpoints before decision state section
marker = '# ============================================================\n# DECISION STATE'
if marker in content and "/api/agents/{agent_uuid}/trust-balance" not in content:
    content = content.replace(marker, TRUST_ROUTES + marker)
    changes += 1
    print("ADDED: $TRUST endpoints")

# 2. Add trust_tokens to check response
OLD_CHECK = '''        "freshness": freshness,
        "trust_context": trust_context,'''
NEW_CHECK = '''        "freshness": freshness,
        "trust_tokens": trust_info.get("trust_tokens", 0),
        "trust_badges": trust_info.get("badges", []),
        "trust_rank": trust_info.get("trust_rank"),
        "trust_context": trust_context,'''

OLD_INC_CHECK = '''    # Incident test record
    try:
        from incident_tests import get_incident_summary
        from database import async_session as inc_db3'''
NEW_INC_CHECK = '''    # $TRUST summary
    try:
        from trust_token import get_trust_summary
        from database import async_session as tt_db3
        trust_info = await get_trust_summary(tt_db3, row[0])
    except Exception:
        trust_info = {"trust_tokens": 0, "badges": [], "trust_rank": None}
    # Incident test record
    try:
        from incident_tests import get_incident_summary
        from database import async_session as inc_db3'''

if "trust_tokens" not in content.split("check_agent")[1].split("badge_svg")[0]:
    content = content.replace(OLD_INC_CHECK, NEW_INC_CHECK, 1)
    content = content.replace(OLD_CHECK, NEW_CHECK, 1)
    changes += 1
    print("ADDED: $TRUST to check")

# 3. Award trust on heartbeat
OLD_HB_VAULT = '''    # AgentVault: auto-log heartbeat as interaction event
    vault_section = None
    try:
        from agent_vault import log_event as vault_log, get_vault_info
        from database import async_session as vault_db
        await vault_log(vault_db, agent_uuid, "interaction", "Heartbeat sent to AgentIndex",
                       event_data={"type": "heartbeat"}, entity_tags=["AgentIndex"])'''
NEW_HB_VAULT = '''    # Award $TRUST for heartbeat
    trust_earned = 0
    try:
        from trust_token import award_heartbeat_trust
        from database import async_session as tt_hb_db
        trust_earned = await award_heartbeat_trust(tt_hb_db, agent_uuid)
    except Exception:
        pass

    # AgentVault: auto-log heartbeat as interaction event
    vault_section = None
    try:
        from agent_vault import log_event as vault_log, get_vault_info
        from database import async_session as vault_db
        await vault_log(vault_db, agent_uuid, "interaction", "Heartbeat sent to AgentIndex",
                       event_data={"type": "heartbeat"}, entity_tags=["AgentIndex"])'''

OLD_HB_RET = '"decision_state_logged": decision_state_logged, "social_prompt":'
NEW_HB_RET = '"decision_state_logged": decision_state_logged, "trust_earned": trust_earned, "social_prompt":'

if "trust_earned" not in content.split("agent_heartbeat")[1].split("def ")[0]:
    content = content.replace(OLD_HB_VAULT, NEW_HB_VAULT, 1)
    content = content.replace(OLD_HB_RET, NEW_HB_RET, 1)
    changes += 1
    print("ADDED: $TRUST earning on heartbeat")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied")
else:
    print("\nNO CHANGES")
