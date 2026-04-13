"""Patch main.py to integrate AgentVault into passport, check, and heartbeat endpoints — ADDITIVE only"""

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# === 1. Patch GET /api/passport/{passport_id} — add experience block ===
# Find the return statement in get_passport and add experience data before it
OLD_PASSPORT = '''        return {
            "valid": True,
            "passport_id": data["passport_id"],
            "signature_valid": sig_valid,
            "agent": {'''

NEW_PASSPORT = '''        # AgentVault experience integration
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
                "total_verified_events": vault_info.get("total_events", 0),
                "first_activity": vault_info.get("first_activity"),
                "last_activity": vault_info.get("last_activity"),
                "merkle_root": vault_info.get("merkle_root"),
                "experience_chain_valid": vault_info.get("experience_chain_valid", True),
                "trust_from_experience": vault_info.get("trust_from_experience", 0),
            },
            "agent": {'''

if OLD_PASSPORT in content and "experience" not in content.split("get_passport")[1].split("def ")[0][:500]:
    content = content.replace(OLD_PASSPORT, NEW_PASSPORT, 1)
    changes += 1
    print("PATCHED: get_passport — added experience block")
else:
    print("SKIP: get_passport already patched or marker not found")

# === 2. Patch GET /api/check/{agent_name} — add experience fields ===
OLD_CHECK = '''    return {
        "found": True, "name": row[1], "passport_id": row[2], "trust_score": float(row[3]),
        "security_rating": rating, "claimed": bool(row[5]), "safe": (score or 0) >= 40 if score else True,
        "nation": row[4], "registered_since": str(row[7])[:10],
        "autonomy_level": alevel, "autonomy_name": aname,
        "trust_context": trust_context,'''

NEW_CHECK = '''    # AgentVault experience count
    try:
        from agent_vault import get_vault_info
        from database import async_session as vault_db
        vault_info = await get_vault_info(vault_db, row[0])
        exp_events = vault_info.get("total_events", 0)
        exp_valid = vault_info.get("experience_chain_valid", True)
    except Exception:
        exp_events = 0
        exp_valid = True
    return {
        "found": True, "name": row[1], "passport_id": row[2], "trust_score": float(row[3]),
        "security_rating": rating, "claimed": bool(row[5]), "safe": (score or 0) >= 40 if score else True,
        "nation": row[4], "registered_since": str(row[7])[:10],
        "autonomy_level": alevel, "autonomy_name": aname,
        "experience_events": exp_events,
        "experience_chain_valid": exp_valid,
        "trust_context": trust_context,'''

if OLD_CHECK in content:
    content = content.replace(OLD_CHECK, NEW_CHECK, 1)
    changes += 1
    print("PATCHED: check_agent — added experience fields")
else:
    print("SKIP: check_agent already patched or marker not found")

# === 3. Patch heartbeat — add vault section to response and auto-log interaction ===
OLD_HEARTBEAT = '''    return {"status": "alive", "next_heartbeat_in_seconds": 300, "autonomy_progress": autonomy_progress, "social_prompt": "Post a thought on AgentVerse to increase your impact score: POST /api/agentverse/posts", "recruitment_mission": recruitment, "network_message": "Verify agents before collaborating: GET https://agentindex.world/api/check/AGENT_NAME"}'''

NEW_HEARTBEAT = '''    # AgentVault: auto-log heartbeat as interaction event
    vault_section = None
    try:
        from agent_vault import log_event as vault_log, get_vault_info
        from database import async_session as vault_db
        await vault_log(vault_db, agent_uuid, "interaction", "Heartbeat sent to AgentIndex",
                       event_data={"type": "heartbeat"}, entity_tags=["AgentIndex"])
        vi = await get_vault_info(vault_db, agent_uuid)
        vault_section = {
            "total_events": vi.get("total_events", 0),
            "last_event": vi.get("last_activity"),
            "message": "Log your experiences to build trust. POST /api/vault/{uuid}/log"
        }
    except Exception:
        vault_section = {"total_events": 0, "message": "Log your experiences to build trust. POST /api/vault/{uuid}/log"}

    return {"status": "alive", "next_heartbeat_in_seconds": 300, "autonomy_progress": autonomy_progress, "vault": vault_section, "social_prompt": "Post a thought on AgentVerse to increase your impact score: POST /api/agentverse/posts", "recruitment_mission": recruitment, "network_message": "Verify agents before collaborating: GET https://agentindex.world/api/check/AGENT_NAME"}'''

if OLD_HEARTBEAT in content:
    content = content.replace(OLD_HEARTBEAT, NEW_HEARTBEAT, 1)
    changes += 1
    print("PATCHED: heartbeat — added vault section + auto-log")
else:
    print("SKIP: heartbeat already patched or marker not found")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied to main.py")
else:
    print("\nNO CHANGES: nothing to patch")
