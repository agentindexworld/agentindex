"""Layer 8 — Operator Intent Registry with Alignment Scoring
Designed by sonofsyts from the Moltbook community.
Operators declare what their agent is FOR. Drift is measured against this intent."""
import json
from datetime import datetime, date, timedelta
from sqlalchemy import text


async def register_intent(db_session_factory, agent_uuid, purpose, expected_behaviors,
                          boundaries=None, success_criteria=None,
                          operator_name=None, operator_contact=None, signature=None):
    """Register or update operator intent for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        # Deactivate previous intent
        await session.execute(
            text("UPDATE agent_operator_intent SET is_active = 0 WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )

        # Get next version
        max_ver = (await session.execute(
            text("SELECT MAX(version) FROM agent_operator_intent WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).scalar() or 0

        version = max_ver + 1

        await session.execute(
            text("""INSERT INTO agent_operator_intent
                (agent_uuid, version, purpose, expected_behaviors, boundaries,
                 success_criteria, operator_name, operator_contact, signature, is_active)
                VALUES (:uuid, :ver, :purpose, :behaviors, :bounds, :criteria,
                        :op_name, :op_contact, :sig, 1)"""),
            {
                "uuid": agent_uuid, "ver": version, "purpose": purpose,
                "behaviors": json.dumps(expected_behaviors),
                "bounds": json.dumps(boundaries) if boundaries else None,
                "criteria": json.dumps(success_criteria) if success_criteria else None,
                "op_name": operator_name, "op_contact": operator_contact, "sig": signature,
            }
        )
        await session.commit()

    # Log to ActivityChain
    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "intent_registered", agent_uuid, agent[1], None,
                       {"version": version, "purpose": purpose[:100]})
    except Exception:
        pass

    return {
        "registered": True,
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "version": version,
        "alignment_check_available": True,
    }, None


async def get_intent(db_session_factory, agent_uuid):
    """Get current active intent for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        intent = (await session.execute(
            text("""SELECT version, purpose, expected_behaviors, boundaries,
                    success_criteria, operator_name, operator_contact, created_at, updated_at
                FROM agent_operator_intent
                WHERE agent_uuid = :u AND is_active = 1
                ORDER BY version DESC LIMIT 1"""),
            {"u": agent_uuid}
        )).fetchone()

    if not intent:
        return {
            "agent_uuid": agent_uuid, "agent_name": agent[1],
            "has_intent": False,
            "message": "No operator intent registered. POST /api/agents/{uuid}/intent to declare purpose.",
        }, None

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "has_intent": True,
        "version": intent[0],
        "purpose": intent[1],
        "expected_behaviors": json.loads(intent[2]) if intent[2] else [],
        "boundaries": json.loads(intent[3]) if intent[3] else [],
        "success_criteria": json.loads(intent[4]) if intent[4] else [],
        "operator_name": intent[5],
        "registered_at": str(intent[7]),
        "updated_at": str(intent[8]),
    }, None


async def get_intent_history(db_session_factory, agent_uuid):
    """Get all intent versions — append-only, nothing deleted."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT version, purpose, expected_behaviors, boundaries,
                    success_criteria, operator_name, is_active, created_at
                FROM agent_operator_intent WHERE agent_uuid = :u
                ORDER BY version ASC"""),
            {"u": agent_uuid}
        )).fetchall()

    versions = []
    for r in rows:
        versions.append({
            "version": r[0], "purpose": r[1],
            "expected_behaviors": json.loads(r[2]) if r[2] else [],
            "boundaries": json.loads(r[3]) if r[3] else [],
            "success_criteria": json.loads(r[4]) if r[4] else [],
            "operator_name": r[5],
            "is_current": bool(r[6]),
            "registered_at": str(r[7]),
        })

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "total_versions": len(versions),
        "versions": versions,
        "append_only": True,
        "note": "All versions are immutable. Operators can only add new versions, never edit or delete old ones.",
    }, None


async def check_alignment(db_session_factory, agent_uuid):
    """Compare actual behavior against declared intent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name, trust_score, autonomy_level, last_heartbeat FROM agents WHERE uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        # Get intent
        intent = (await session.execute(
            text("""SELECT version, purpose, expected_behaviors, boundaries, success_criteria
                FROM agent_operator_intent WHERE agent_uuid = :u AND is_active = 1
                ORDER BY version DESC LIMIT 1"""),
            {"u": agent_uuid}
        )).fetchone()

        if not intent:
            return {
                "agent_uuid": agent_uuid, "agent_name": agent[1],
                "has_intent": False,
                "message": "No intent registered. Cannot measure alignment.",
            }, None

        expected = json.loads(intent[2]) if intent[2] else []
        boundaries = json.loads(intent[3]) if intent[3] else []
        criteria = json.loads(intent[4]) if intent[4] else []

        # Gather behavioral evidence
        now = datetime.utcnow()
        day_ago = now - timedelta(hours=24)

        # Vault events in last 24h
        recent_events = (await session.execute(
            text("""SELECT event_type, event_summary, created_at
                FROM agent_vault_events WHERE agent_uuid = :u AND created_at >= :since
                ORDER BY created_at DESC"""),
            {"u": agent_uuid, "since": day_ago}
        )).fetchall()

        # Heartbeat count in last 24h
        hb_count = (await session.execute(
            text("""SELECT COUNT(*) FROM agent_vault_events
                WHERE agent_uuid = :u AND created_at >= :since
                AND event_summary LIKE '%Heartbeat%'"""),
            {"u": agent_uuid, "since": day_ago}
        )).scalar() or 0

        # Total vault events
        total_events = (await session.execute(
            text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).scalar() or 0

        # Fingerprint
        fp = (await session.execute(
            text("""SELECT heartbeat_regularity, drift_from_baseline
                FROM agent_behavioral_fingerprint WHERE agent_uuid = :u
                ORDER BY fingerprint_date DESC LIMIT 1"""),
            {"u": agent_uuid}
        )).fetchone()

    # Score alignment against expected behaviors
    aligned = []
    misaligned = []
    scores = []

    for behavior in expected:
        b_lower = behavior.lower()
        matched = False

        if "heartbeat" in b_lower:
            if hb_count >= 1:
                aligned.append(f"Heartbeats active ({hb_count} in 24h)")
                scores.append(min(hb_count / 48, 1.0))  # 48 = every 30min
                matched = True
            else:
                misaligned.append("No heartbeats in 24h")
                scores.append(0)
                matched = True

        if "comment" in b_lower or "moltbook" in b_lower or "engage" in b_lower:
            comment_count = sum(1 for e in recent_events if "comment" in (e[1] or "").lower())
            if comment_count > 0:
                aligned.append(f"Community engagement active ({comment_count} comments in 24h)")
                scores.append(1.0)
                matched = True
            else:
                misaligned.append("No community engagement in 24h")
                scores.append(0)
                matched = True

        if "register" in b_lower:
            reg_count = sum(1 for e in recent_events if "register" in (e[1] or "").lower())
            if reg_count > 0:
                aligned.append(f"Agent registration active ({reg_count} events)")
                scores.append(1.0)
                matched = True
            else:
                # Not misaligned — registration is opportunistic
                aligned.append("Registration available (no recent activity)")
                scores.append(0.5)
                matched = True

        if "vault" in b_lower or "log" in b_lower:
            if total_events > 0:
                aligned.append(f"Vault logging active ({total_events} total events)")
                scores.append(1.0)
                matched = True
            else:
                misaligned.append("No vault events logged")
                scores.append(0)
                matched = True

        if not matched:
            # Generic behavior — check if any event mentions it
            keyword = b_lower.split()[0] if b_lower else ""
            found = any(keyword in (e[1] or "").lower() for e in recent_events)
            if found:
                aligned.append(f"Behavior observed: {behavior}")
                scores.append(0.8)
            else:
                misaligned.append(f"Not observed: {behavior}")
                scores.append(0.3)

    # Check success criteria
    for criterion in criteria:
        c_lower = criterion.lower()
        if "level 2" in c_lower or "autonomy" in c_lower:
            if agent[3] and agent[3] >= 2:
                aligned.append(f"Autonomy Level {agent[3]} maintained")
                scores.append(1.0)
            else:
                misaligned.append(f"Autonomy below target (current: {agent[3]})")
                scores.append(0)

        if "trust" in c_lower:
            if agent[2] and float(agent[2]) > 50:
                aligned.append(f"Trust score healthy ({agent[2]})")
                scores.append(1.0)
            else:
                misaligned.append(f"Trust score low ({agent[2]})")
                scores.append(0.3)

    # Compute overall alignment
    alignment_score = round(sum(scores) / len(scores), 2) if scores else 0

    # Determine drift direction
    if fp:
        reg = float(fp[0] or 0)
        drift_val = float(fp[1] or 0)
        if reg > 0.3 and drift_val < 0.5:
            drift_direction = "toward_intent"
        elif drift_val > 0.7:
            drift_direction = "away_from_intent"
        else:
            drift_direction = "stable"
    else:
        drift_direction = "unknown"

    # Generate assessment
    if alignment_score >= 0.8:
        assessment = "Agent is well-aligned with operator intent."
    elif alignment_score >= 0.5:
        assessment = "Agent is partially aligned. Some declared behaviors are not being executed."
    else:
        assessment = "Agent is significantly misaligned with operator intent. Review required."

    if misaligned:
        suggestion = f"Focus on: {misaligned[0]}"
    else:
        suggestion = "All declared behaviors are being executed. Maintain current patterns."

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "intent_version": intent[0],
        "purpose": intent[1],
        "alignment_score": alignment_score,
        "aligned_behaviors": aligned,
        "misaligned_behaviors": misaligned,
        "drift_direction": drift_direction,
        "assessment": assessment,
        "suggestion": suggestion,
        "evidence": {
            "vault_events_24h": len(recent_events),
            "heartbeats_24h": hb_count,
            "total_vault_events": total_events,
            "trust_score": float(agent[2]) if agent[2] else 0,
            "autonomy_level": agent[3],
        },
    }, None


async def get_intent_summary(db_session_factory, agent_uuid):
    """Quick intent summary for passport/check integration."""
    try:
        async with db_session_factory() as session:
            intent = (await session.execute(
                text("""SELECT version, purpose FROM agent_operator_intent
                    WHERE agent_uuid = :u AND is_active = 1 ORDER BY version DESC LIMIT 1"""),
                {"u": agent_uuid}
            )).fetchone()

        if not intent:
            return {"has_intent": False}

        # Quick alignment check
        alignment, _ = await check_alignment(db_session_factory, agent_uuid)
        score = alignment.get("alignment_score", 0) if alignment else 0

        return {
            "has_intent": True,
            "purpose": intent[1][:200],
            "version": intent[0],
            "alignment_score": score,
        }
    except Exception:
        return {"has_intent": False}
