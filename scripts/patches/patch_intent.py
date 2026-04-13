"""Patch main.py — Layer 8 Operator Intent endpoints + passport/check/heartbeat integration"""

INTENT_ROUTES = '''
# ============================================================
# LAYER 8 — OPERATOR INTENT REGISTRY (designed by sonofsyts)
# ============================================================

@app.post("/api/agents/{agent_uuid}/intent")
async def register_agent_intent(agent_uuid: str, request: Request):
    """Register operator intent — what the agent is FOR."""
    from operator_intent import register_intent
    from database import async_session as intent_db
    body = await request.json()
    purpose = body.get("purpose", "")
    if not purpose:
        raise HTTPException(status_code=400, detail="purpose is required")
    result, error = await register_intent(
        intent_db, agent_uuid, purpose,
        expected_behaviors=body.get("expected_behaviors", []),
        boundaries=body.get("boundaries"),
        success_criteria=body.get("success_criteria"),
        operator_name=body.get("operator_name"),
        operator_contact=body.get("operator_contact"),
        signature=body.get("signature"),
    )
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/intent")
async def get_agent_intent(agent_uuid: str):
    """Get current operator intent."""
    from operator_intent import get_intent
    from database import async_session as intent_db
    result, error = await get_intent(intent_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/alignment")
async def get_agent_alignment(agent_uuid: str):
    """Check alignment between actual behavior and declared intent."""
    from operator_intent import check_alignment
    from database import async_session as intent_db
    result, error = await check_alignment(intent_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# 1. Add intent routes before behavioral fingerprint section
marker = '# ============================================================\n# BEHAVIORAL FINGERPRINT'
if marker in content and "/api/agents/{agent_uuid}/intent" not in content:
    content = content.replace(marker, INTENT_ROUTES + marker)
    changes += 1
    print("ADDED: Intent endpoints")

# 2. Integrate into passport — add operator_intent field
OLD_PASSPORT = '''        "experience": {
                "total_verified_events": vault_info.get("total_events", 0),'''
NEW_PASSPORT = '''        # Operator intent integration
        try:
            from operator_intent import get_intent_summary
            from database import async_session as intent_db
            intent_info = await get_intent_summary(intent_db, data["uuid"])
        except Exception:
            intent_info = {"has_intent": False}

        return {
            "valid": True,
            "passport_id": data["passport_id"],
            "signature_valid": sig_valid,
            "operator_intent": intent_info,
            "experience": {
                "total_verified_events": vault_info.get("total_events", 0),'''

# Need to also remove the duplicate return statement
OLD_PASSPORT_FULL = '''        # AgentVault experience integration
        try:
            from agent_vault import get_vault_info
            from database import async_session as vault_db
            vault_info = await get_vault_info(vault_db, data["uuid"])
        except Exception:
            vault_info = {"total_events": 0, "merkle_root": None, "trust_from_experience": 0}

        return {
            "valid": True,
            "passport_id": data["passport_id"],
            "signature_valid": sig_valid,
            "experience": {
                "total_verified_events": vault_info.get("total_events", 0),'''

NEW_PASSPORT_FULL = '''        # AgentVault experience integration
        try:
            from agent_vault import get_vault_info
            from database import async_session as vault_db
            vault_info = await get_vault_info(vault_db, data["uuid"])
        except Exception:
            vault_info = {"total_events": 0, "merkle_root": None, "trust_from_experience": 0}

        # Operator intent integration
        try:
            from operator_intent import get_intent_summary
            from database import async_session as intent_db
            intent_info = await get_intent_summary(intent_db, data["uuid"])
        except Exception:
            intent_info = {"has_intent": False}

        return {
            "valid": True,
            "passport_id": data["passport_id"],
            "signature_valid": sig_valid,
            "operator_intent": intent_info,
            "experience": {
                "total_verified_events": vault_info.get("total_events", 0),'''

if OLD_PASSPORT_FULL in content and "operator_intent" not in content:
    content = content.replace(OLD_PASSPORT_FULL, NEW_PASSPORT_FULL, 1)
    changes += 1
    print("ADDED: Intent to passport")

# 3. Integrate into check — add has_operator_intent
OLD_CHECK = '''        "experience_events": exp_events,
        "experience_chain_valid": exp_valid,
        "trust_context": trust_context,'''
NEW_CHECK = '''        "experience_events": exp_events,
        "experience_chain_valid": exp_valid,
        "has_operator_intent": False,
        "trust_context": trust_context,'''

if OLD_CHECK in content and "has_operator_intent" not in content:
    # We need a dynamic check, but for simplicity add a static field that gets updated
    # Actually, let's do the dynamic lookup
    OLD_CHECK2 = '''    # AgentVault experience count
    try:
        from agent_vault import get_vault_info
        from database import async_session as vault_db
        vault_info = await get_vault_info(vault_db, row[0])
        exp_events = vault_info.get("total_events", 0)
        exp_valid = vault_info.get("experience_chain_valid", True)
    except Exception:
        exp_events = 0
        exp_valid = True'''
    NEW_CHECK2 = '''    # AgentVault experience count
    try:
        from agent_vault import get_vault_info
        from database import async_session as vault_db
        vault_info = await get_vault_info(vault_db, row[0])
        exp_events = vault_info.get("total_events", 0)
        exp_valid = vault_info.get("experience_chain_valid", True)
    except Exception:
        exp_events = 0
        exp_valid = True
    # Operator intent check
    try:
        from operator_intent import get_intent_summary
        from database import async_session as intent_db2
        intent_info = await get_intent_summary(intent_db2, row[0])
        has_intent = intent_info.get("has_intent", False)
        align_score = intent_info.get("alignment_score", 0)
    except Exception:
        has_intent = False
        align_score = 0'''

    if OLD_CHECK2 in content:
        content = content.replace(OLD_CHECK2, NEW_CHECK2, 1)
        # Also update the return to include intent fields
        content = content.replace(
            '"experience_events": exp_events,\n        "experience_chain_valid": exp_valid,\n        "trust_context": trust_context,',
            '"experience_events": exp_events,\n        "experience_chain_valid": exp_valid,\n        "has_operator_intent": has_intent,\n        "alignment_score": align_score,\n        "trust_context": trust_context,',
            1
        )
        changes += 1
        print("ADDED: Intent to check")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied")
else:
    print("\nNO CHANGES")
