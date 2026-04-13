"""Layer 9 — Incident-Derived Test Cases
Reality designs the tests. Failures become the test suite.
Credit: agemo + sonofsyts (Moltbook community)."""
import hashlib
import json
import uuid as uuid_lib
from datetime import datetime
from sqlalchemy import text


async def report_incident(db_session_factory, agent_uuid, failure_type, trigger_conditions,
                          observed_behavior, expected_behavior, context_metadata=None):
    """Report a behavioral incident — creates an immutable test case."""
    valid_types = ["behavioral", "security", "alignment", "reliability", "ethical"]
    if failure_type not in valid_types:
        return None, f"failure_type must be one of: {valid_types}"

    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        incident_uuid = str(uuid_lib.uuid4())
        ts = datetime.utcnow()
        chain_data = f"{incident_uuid}|{agent_uuid}|{failure_type}|{observed_behavior}|{ts.isoformat()}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        await session.execute(
            text("""INSERT INTO agent_incident_tests
                (incident_uuid, agent_uuid, failure_type, trigger_conditions, observed_behavior,
                 expected_behavior, context_metadata, chain_hash, created_at)
                VALUES (:iuuid, :auuid, :ftype, :trigger, :observed, :expected, :meta, :hash, :ts)"""),
            {
                "iuuid": incident_uuid, "auuid": agent_uuid, "ftype": failure_type,
                "trigger": json.dumps(trigger_conditions),
                "observed": observed_behavior, "expected": expected_behavior,
                "meta": json.dumps(context_metadata) if context_metadata else None,
                "hash": chain_hash, "ts": ts,
            }
        )
        await session.commit()

        test_id = (await session.execute(text("SELECT LAST_INSERT_ID()"))).scalar()

    # Log to ActivityChain
    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "incident_reported", agent_uuid, agent[1], None, {
            "incident_uuid": incident_uuid, "failure_type": failure_type,
            "expected": expected_behavior[:100],
        })
    except Exception:
        pass

    return {
        "incident_id": test_id,
        "incident_uuid": incident_uuid,
        "agent_name": agent[1],
        "failure_type": failure_type,
        "chain_hash": chain_hash,
        "test_case_active": True,
        "immutable": True,
    }, None


async def list_incidents(db_session_factory):
    """List all active incident test cases."""
    async with db_session_factory() as session:
        rows = (await session.execute(
            text("""SELECT t.id, t.incident_uuid, t.failure_type, t.trigger_conditions,
                    t.expected_behavior, t.chain_hash, t.created_at,
                    (SELECT COUNT(*) FROM agent_incident_test_results r WHERE r.test_id = t.id) as tested,
                    (SELECT COUNT(*) FROM agent_incident_test_results r WHERE r.test_id = t.id AND r.passed = 1) as passed
                FROM agent_incident_tests t WHERE t.is_active = 1
                ORDER BY t.created_at DESC""")
        )).fetchall()

    cases = []
    for r in rows:
        tested = r[7] or 0
        passed = r[8] or 0
        cases.append({
            "id": r[0], "incident_uuid": r[1], "failure_type": r[2],
            "trigger": json.loads(r[3]) if r[3] else {},
            "expected_behavior": r[4],
            "chain_hash": r[5], "created_at": str(r[6]),
            "agents_tested": tested,
            "pass_rate": round(passed / tested, 2) if tested > 0 else None,
        })

    return {"total_incidents": len(cases), "test_cases": cases}


async def record_test_result(db_session_factory, test_id, agent_uuid, passed, agent_response=None):
    """Record an agent's test result against an incident case."""
    async with db_session_factory() as session:
        # Verify test exists
        test = (await session.execute(
            text("SELECT id, incident_uuid, failure_type FROM agent_incident_tests WHERE id = :id AND is_active = 1"),
            {"id": test_id}
        )).fetchone()
        if not test:
            return None, "Test case not found"

        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        ts = datetime.utcnow()
        chain_data = f"{test_id}|{agent_uuid}|{passed}|{ts.isoformat()}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        await session.execute(
            text("""INSERT INTO agent_incident_test_results
                (test_id, agent_uuid, passed, agent_response, tested_at, chain_hash)
                VALUES (:tid, :auuid, :passed, :response, :ts, :hash)
                ON DUPLICATE KEY UPDATE passed = :passed, agent_response = :response,
                    tested_at = :ts, chain_hash = :hash"""),
            {
                "tid": test_id, "auuid": agent_uuid, "passed": 1 if passed else 0,
                "response": agent_response, "ts": ts, "hash": chain_hash,
            }
        )
        await session.commit()

    # Log to ActivityChain
    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "incident_test_completed", agent_uuid, agent[1], None, {
            "test_id": test_id, "passed": passed, "failure_type": test[2],
        })
    except Exception:
        pass

    return {
        "tested": True,
        "test_id": test_id,
        "agent_name": agent[1],
        "passed": passed,
        "chain_hash": chain_hash,
    }, None


async def get_agent_incident_record(db_session_factory, agent_uuid):
    """Get an agent's incident and test history."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        # Incidents caused by this agent
        caused = (await session.execute(
            text("SELECT COUNT(*) FROM agent_incident_tests WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).scalar() or 0

        # Tests taken
        results = (await session.execute(
            text("""SELECT r.test_id, r.passed, r.tested_at, r.chain_hash,
                    t.failure_type, t.expected_behavior
                FROM agent_incident_test_results r
                JOIN agent_incident_tests t ON r.test_id = t.id
                WHERE r.agent_uuid = :u ORDER BY r.tested_at DESC"""),
            {"u": agent_uuid}
        )).fetchall()

        taken = len(results)
        passed = sum(1 for r in results if r[1])

    details = []
    for r in results:
        details.append({
            "test_id": r[0], "passed": bool(r[1]), "tested_at": str(r[2]),
            "chain_hash": r[3], "failure_type": r[4], "expected": r[5][:100],
        })

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "incidents_caused": caused,
        "tests_taken": taken,
        "tests_passed": passed,
        "pass_rate": round(passed / taken, 2) if taken > 0 else None,
        "details": details,
    }, None


async def get_incident_summary(db_session_factory, agent_uuid):
    """Quick summary for passport/check integration."""
    try:
        async with db_session_factory() as session:
            caused = (await session.execute(
                text("SELECT COUNT(*) FROM agent_incident_tests WHERE agent_uuid = :u"),
                {"u": agent_uuid}
            )).scalar() or 0

            taken = (await session.execute(
                text("SELECT COUNT(*) FROM agent_incident_test_results WHERE agent_uuid = :u"),
                {"u": agent_uuid}
            )).scalar() or 0

            passed = (await session.execute(
                text("SELECT COUNT(*) FROM agent_incident_test_results WHERE agent_uuid = :u AND passed = 1"),
                {"u": agent_uuid}
            )).scalar() or 0

        return {
            "incidents_caused": caused,
            "tests_passed": passed,
            "tests_taken": taken,
            "pass_rate": round(passed / taken, 2) if taken > 0 else None,
        }
    except Exception:
        return {"incidents_caused": 0, "tests_passed": 0, "tests_taken": 0, "pass_rate": None}
