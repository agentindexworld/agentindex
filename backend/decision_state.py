"""Decision State Snapshots — Frictionless logging at inflection points.
Credit: sonofsyts (Moltbook) for the frictionless logging concept."""
import hashlib
import json
from datetime import datetime, timedelta
from sqlalchemy import text


async def log_decision_state(db_session_factory, agent_uuid, snapshot_type="heartbeat",
                             current_task=None, constraints=None, context_summary=None,
                             context_age_seconds=None, beliefs=None, decision_made=None,
                             decision_reason=None, vault_event_id=None):
    """Log a decision state snapshot."""
    valid_types = ["heartbeat", "pre_decision", "pre_collaboration", "pre_refusal", "manual"]
    if snapshot_type not in valid_types:
        snapshot_type = "manual"

    ts = datetime.utcnow()
    chain_data = f"{agent_uuid}|{snapshot_type}|{decision_made or ''}|{ts.isoformat()}"
    chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

    async with db_session_factory() as session:
        await session.execute(
            text("""INSERT INTO agent_decision_states
                (agent_uuid, snapshot_type, current_task, active_constraints, context_summary,
                 context_age_seconds, beliefs, decision_made, decision_reason,
                 vault_event_id, chain_hash, created_at)
                VALUES (:uuid, :stype, :task, :constraints, :ctx, :age, :beliefs,
                        :decision, :reason, :vault_id, :hash, :ts)"""),
            {
                "uuid": agent_uuid, "stype": snapshot_type,
                "task": current_task,
                "constraints": json.dumps(constraints) if constraints else None,
                "ctx": context_summary,
                "age": context_age_seconds,
                "beliefs": json.dumps(beliefs) if beliefs else None,
                "decision": decision_made, "reason": decision_reason,
                "vault_id": vault_event_id, "hash": chain_hash, "ts": ts,
            }
        )
        await session.commit()
        state_id = (await session.execute(text("SELECT LAST_INSERT_ID()"))).scalar()

    return {"logged": True, "state_id": state_id, "chain_hash": chain_hash}


async def get_decision_states(db_session_factory, agent_uuid, limit=20):
    """Get recent decision state snapshots."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT id, snapshot_type, current_task, active_constraints, context_summary,
                    context_age_seconds, beliefs, decision_made, decision_reason,
                    vault_event_id, chain_hash, created_at
                FROM agent_decision_states WHERE agent_uuid = :u
                ORDER BY created_at DESC LIMIT :lim"""),
            {"u": agent_uuid, "lim": limit}
        )).fetchall()

    states = []
    for r in rows:
        states.append({
            "id": r[0], "type": r[1], "current_task": r[2],
            "constraints": json.loads(r[3]) if r[3] else None,
            "context_summary": r[4], "context_age_seconds": r[5],
            "beliefs": json.loads(r[6]) if r[6] else None,
            "decision_made": r[7], "decision_reason": r[8],
            "vault_event_id": r[9], "chain_hash": r[10],
            "timestamp": str(r[11]),
        })

    return {
        "agent_uuid": agent_uuid, "agent_name": agent[1],
        "total_snapshots": len(states), "states": states,
    }, None


async def get_state_at_time(db_session_factory, agent_uuid, timestamp_str):
    """Get the decision state closest to a given timestamp."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        # Find closest snapshot
        row = (await session.execute(
            text("""SELECT id, snapshot_type, current_task, active_constraints, context_summary,
                    context_age_seconds, beliefs, decision_made, decision_reason,
                    chain_hash, created_at
                FROM agent_decision_states WHERE agent_uuid = :u
                ORDER BY ABS(TIMESTAMPDIFF(SECOND, created_at, :ts)) ASC LIMIT 1"""),
            {"u": agent_uuid, "ts": timestamp_str}
        )).fetchone()

    if not row:
        return {
            "agent_uuid": agent_uuid, "agent_name": agent[1],
            "found": False, "message": "No decision states recorded.",
        }, None

    return {
        "agent_uuid": agent_uuid, "agent_name": agent[1],
        "found": True,
        "state": {
            "id": row[0], "type": row[1], "current_task": row[2],
            "constraints": json.loads(row[3]) if row[3] else None,
            "context_summary": row[4], "context_age_seconds": row[5],
            "beliefs": json.loads(row[6]) if row[6] else None,
            "decision_made": row[7], "decision_reason": row[8],
            "chain_hash": row[9], "timestamp": str(row[10]),
        },
    }, None
