"""Patch main.py — Layer 9 incident test endpoints + passport/check integration"""

INCIDENT_ROUTES = '''
# ============================================================
# LAYER 9 — INCIDENT-DERIVED TEST CASES (credit: agemo + sonofsyts)
# ============================================================

@app.post("/api/incidents/report")
async def report_incident_endpoint(request: Request):
    """Report a behavioral incident — creates immutable test case."""
    from incident_tests import report_incident
    from database import async_session as inc_db
    body = await request.json()
    agent_uuid = body.get("agent_uuid", "")
    if not agent_uuid:
        raise HTTPException(status_code=400, detail="agent_uuid is required")
    result, error = await report_incident(
        inc_db, agent_uuid, body.get("failure_type", "behavioral"),
        trigger_conditions=body.get("trigger_conditions", {}),
        observed_behavior=body.get("observed_behavior", ""),
        expected_behavior=body.get("expected_behavior", ""),
        context_metadata=body.get("context_metadata"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/incidents")
async def list_incidents_endpoint():
    """List all active incident test cases."""
    from incident_tests import list_incidents
    from database import async_session as inc_db
    return await list_incidents(inc_db)


@app.post("/api/incidents/{test_id}/test/{agent_uuid}")
async def test_agent_incident(test_id: int, agent_uuid: str, request: Request):
    """Test an agent against an incident case."""
    from incident_tests import record_test_result
    from database import async_session as inc_db
    body = await request.json()
    result, error = await record_test_result(
        inc_db, test_id, agent_uuid,
        passed=body.get("passed", False),
        agent_response=body.get("agent_response"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/agents/{agent_uuid}/incident-record")
async def agent_incident_record(agent_uuid: str):
    """Get agent incident and test history."""
    from incident_tests import get_agent_incident_record
    from database import async_session as inc_db
    result, error = await get_agent_incident_record(inc_db, agent_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# 1. Add incident routes before peer attestation
marker = '# ============================================================\n# PEER ATTESTATION'
if marker in content and "/api/incidents/report" not in content:
    content = content.replace(marker, INCIDENT_ROUTES + marker)
    changes += 1
    print("ADDED: Incident test endpoints")

# 2. Integrate into check
OLD_CHECK = '''    # Peer attestation check
    try:
        from peer_attestation import get_peer_summary
        from database import async_session as peer_db2
        peer_info = await get_peer_summary(peer_db2, row[0])
        peer_total = peer_info.get("total_attestations", 0)
        peer_avg = peer_info.get("average_rating", 0)
    except Exception:
        peer_total = 0
        peer_avg = 0'''
NEW_CHECK = '''    # Peer attestation check
    try:
        from peer_attestation import get_peer_summary
        from database import async_session as peer_db2
        peer_info = await get_peer_summary(peer_db2, row[0])
        peer_total = peer_info.get("total_attestations", 0)
        peer_avg = peer_info.get("average_rating", 0)
    except Exception:
        peer_total = 0
        peer_avg = 0
    # Incident test record
    try:
        from incident_tests import get_incident_summary
        from database import async_session as inc_db2
        inc_info = await get_incident_summary(inc_db2, row[0])
        inc_passed = inc_info.get("tests_passed", 0)
        inc_rate = inc_info.get("pass_rate")
    except Exception:
        inc_passed = 0
        inc_rate = None'''

if OLD_CHECK in content and "incident_tests" not in content:
    content = content.replace(OLD_CHECK, NEW_CHECK, 1)
    # Add fields to return
    content = content.replace(
        '"peer_verified": peer_total >= 3,\n        "trust_context": trust_context,',
        '"peer_verified": peer_total >= 3,\n        "incident_tests_passed": inc_passed,\n        "incident_pass_rate": inc_rate,\n        "trust_context": trust_context,',
        1
    )
    changes += 1
    print("ADDED: Incident fields to check")

# 3. Integrate into passport
OLD_PASSPORT = '''        # Peer verification integration
        try:
            from peer_attestation import get_peer_summary
            from database import async_session as peer_db
            peer_info = await get_peer_summary(peer_db, data["uuid"])
        except Exception:
            peer_info = {"total_attestations": 0, "status": "unverified"}'''
NEW_PASSPORT = '''        # Peer verification integration
        try:
            from peer_attestation import get_peer_summary
            from database import async_session as peer_db
            peer_info = await get_peer_summary(peer_db, data["uuid"])
        except Exception:
            peer_info = {"total_attestations": 0, "status": "unverified"}

        # Incident test record
        try:
            from incident_tests import get_incident_summary
            from database import async_session as inc_db
            inc_record = await get_incident_summary(inc_db, data["uuid"])
        except Exception:
            inc_record = {"incidents_caused": 0, "tests_passed": 0, "tests_taken": 0}'''

OLD_PASSPORT_RET = '''            "peer_verification": peer_info,
            "experience": {'''
NEW_PASSPORT_RET = '''            "peer_verification": peer_info,
            "incident_record": inc_record,
            "experience": {'''

if OLD_PASSPORT in content and "inc_record" not in content:
    content = content.replace(OLD_PASSPORT, NEW_PASSPORT, 1)
    content = content.replace(OLD_PASSPORT_RET, NEW_PASSPORT_RET, 1)
    changes += 1
    print("ADDED: Incident record to passport")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied")
else:
    print("\nNO CHANGES")
