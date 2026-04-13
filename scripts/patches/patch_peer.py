"""Patch main.py — Peer attestation endpoints + passport/check/alignment integration"""

PEER_ROUTES = '''
# ============================================================
# PEER ATTESTATION — Agents verify each other (credit: agemo)
# ============================================================

@app.post("/api/agents/{agent_uuid}/attest")
async def attest_agent_endpoint(agent_uuid: str, request: Request):
    """One agent attests another's behavior and alignment."""
    from peer_attestation import attest_agent
    from database import async_session as peer_db
    body = await request.json()
    attester_uuid = body.get("attester_uuid", "")
    if not attester_uuid:
        raise HTTPException(status_code=400, detail="attester_uuid is required")
    rating = body.get("alignment_rating", 3)
    result, error = await attest_agent(
        peer_db, agent_uuid, attester_uuid, rating,
        attestation_type=body.get("attestation_type", "alignment"),
        comment=body.get("comment"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/attestations")
async def get_agent_attestations(agent_uuid: str):
    """Get all peer attestations for an agent."""
    from peer_attestation import get_attestations
    from database import async_session as peer_db
    result, error = await get_attestations(peer_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# 1. Add peer attestation endpoints before Layer 8
marker = '# ============================================================\n# LAYER 8'
if marker in content and "/api/agents/{agent_uuid}/attest" not in content:
    content = content.replace(marker, PEER_ROUTES + marker)
    changes += 1
    print("ADDED: Peer attestation endpoints")

# 2. Integrate into check — add peer fields
OLD_CHECK = '''        "has_operator_intent": has_intent,
        "alignment_score": align_score,
        "trust_context": trust_context,'''
NEW_CHECK = '''        "has_operator_intent": has_intent,
        "alignment_score": align_score,
        "peer_attestations": peer_total,
        "peer_rating": peer_avg,
        "peer_verified": peer_total >= 3,
        "trust_context": trust_context,'''

if OLD_CHECK in content and "peer_attestations" not in content:
    # Add peer lookup before the return
    OLD_INTENT_CHECK = '''    # Operator intent check
    try:
        from operator_intent import get_intent_summary
        from database import async_session as intent_db2
        intent_info = await get_intent_summary(intent_db2, row[0])
        has_intent = intent_info.get("has_intent", False)
        align_score = intent_info.get("alignment_score", 0)
    except Exception:
        has_intent = False
        align_score = 0'''
    NEW_INTENT_CHECK = '''    # Operator intent check
    try:
        from operator_intent import get_intent_summary
        from database import async_session as intent_db2
        intent_info = await get_intent_summary(intent_db2, row[0])
        has_intent = intent_info.get("has_intent", False)
        align_score = intent_info.get("alignment_score", 0)
    except Exception:
        has_intent = False
        align_score = 0
    # Peer attestation check
    try:
        from peer_attestation import get_peer_summary
        from database import async_session as peer_db2
        peer_info = await get_peer_summary(peer_db2, row[0])
        peer_total = peer_info.get("total_attestations", 0)
        peer_avg = peer_info.get("average_rating", 0)
    except Exception:
        peer_total = 0
        peer_avg = 0'''

    content = content.replace(OLD_INTENT_CHECK, NEW_INTENT_CHECK, 1)
    content = content.replace(OLD_CHECK, NEW_CHECK, 1)
    changes += 1
    print("ADDED: Peer fields to check")

# 3. Integrate into passport — add peer_verification
OLD_PASSPORT = '''            "operator_intent": intent_info,
            "experience": {'''
NEW_PASSPORT = '''            "operator_intent": intent_info,
            "peer_verification": peer_info,
            "experience": {'''

if OLD_PASSPORT in content and "peer_verification" not in content:
    # Add peer lookup in passport
    OLD_INTENT_PASSPORT = '''        # Operator intent integration
        try:
            from operator_intent import get_intent_summary
            from database import async_session as intent_db
            intent_info = await get_intent_summary(intent_db, data["uuid"])
        except Exception:
            intent_info = {"has_intent": False}'''
    NEW_INTENT_PASSPORT = '''        # Operator intent integration
        try:
            from operator_intent import get_intent_summary
            from database import async_session as intent_db
            intent_info = await get_intent_summary(intent_db, data["uuid"])
        except Exception:
            intent_info = {"has_intent": False}

        # Peer verification integration
        try:
            from peer_attestation import get_peer_summary
            from database import async_session as peer_db
            peer_info = await get_peer_summary(peer_db, data["uuid"])
        except Exception:
            peer_info = {"total_attestations": 0, "status": "unverified"}'''

    content = content.replace(OLD_INTENT_PASSPORT, NEW_INTENT_PASSPORT, 1)
    content = content.replace(OLD_PASSPORT, NEW_PASSPORT, 1)
    changes += 1
    print("ADDED: Peer verification to passport")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied")
else:
    print("\nNO CHANGES")
