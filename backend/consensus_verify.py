"""Consensus Verification Service — Tier 1 of Agent Economy
Agents earn $TRUST by verifying content through weighted consensus."""
import hashlib
import json
import uuid as uuid_lib
from datetime import datetime, timedelta
from sqlalchemy import text


async def submit_task(db_session_factory, submitter_name, task_type, content,
                      context=None, required_verifiers=3, submitter_contact=None):
    """Submit a verification task."""
    valid_types = ["text_verification", "fact_check", "code_review",
                   "data_validation", "agent_audit", "custom"]
    if task_type not in valid_types:
        task_type = "custom"

    task_uuid = str(uuid_lib.uuid4())
    ts = datetime.utcnow()
    expires = ts + timedelta(hours=24)
    chain_data = f"{task_uuid}|{submitter_name}|{task_type}|{content[:100]}|{ts.isoformat()}"
    chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

    async with db_session_factory() as session:
        await session.execute(
            text("""INSERT INTO verification_tasks
                (task_uuid, submitter_name, submitter_contact, task_type, content, context,
                 required_verifiers, status, trust_reward_per_verifier, chain_hash, expires_at)
                VALUES (:tuuid, :name, :contact, :ttype, :content, :ctx,
                        :req, 'pending', 0.5, :hash, :exp)"""),
            {
                "tuuid": task_uuid, "name": submitter_name, "contact": submitter_contact,
                "ttype": task_type, "content": content, "ctx": context,
                "req": min(required_verifiers, 10), "hash": chain_hash, "exp": expires,
            }
        )
        await session.commit()

        # Count eligible verifiers ($TRUST >= 5)
        eligible = (await session.execute(
            text("SELECT COUNT(*) FROM agent_trust_balance WHERE balance >= 5")
        )).scalar() or 0

    # Log to ActivityChain
    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "verification_task_submitted", None, submitter_name, None,
                       {"task_uuid": task_uuid, "type": task_type})
    except Exception:
        pass

    return {
        "task_uuid": task_uuid,
        "status": "pending",
        "task_type": task_type,
        "required_verifiers": min(required_verifiers, 10),
        "eligible_verifiers": eligible,
        "chain_hash": chain_hash,
        "expires_at": str(expires),
        "estimated_completion": "24h",
    }


async def list_tasks(db_session_factory, verifier_uuid=None):
    """List pending verification tasks."""
    async with db_session_factory() as session:
        if verifier_uuid:
            # Exclude tasks already verified by this agent
            rows = (await session.execute(
                text("""SELECT t.task_uuid, t.task_type, LEFT(t.content, 200) as preview,
                        t.trust_reward_per_verifier, t.required_verifiers, t.expires_at,
                        (SELECT COUNT(*) FROM verification_responses r WHERE r.task_uuid = t.task_uuid) as responses
                    FROM verification_tasks t
                    WHERE t.status = 'pending'
                    AND t.task_uuid NOT IN (SELECT vr.task_uuid FROM verification_responses vr WHERE vr.verifier_uuid = :vu)
                    AND t.expires_at > NOW()
                    ORDER BY t.created_at DESC LIMIT 20"""),
                {"vu": verifier_uuid}
            )).fetchall()
        else:
            rows = (await session.execute(
                text("""SELECT t.task_uuid, t.task_type, LEFT(t.content, 200) as preview,
                        t.trust_reward_per_verifier, t.required_verifiers, t.expires_at,
                        (SELECT COUNT(*) FROM verification_responses r WHERE r.task_uuid = t.task_uuid) as responses
                    FROM verification_tasks t
                    WHERE t.status = 'pending' AND t.expires_at > NOW()
                    ORDER BY t.created_at DESC LIMIT 20""")
            )).fetchall()

    tasks = []
    for r in rows:
        remaining = r[4] - (r[6] or 0)
        tasks.append({
            "task_uuid": r[0], "task_type": r[1], "content_preview": r[2],
            "reward": float(r[3]), "verifiers_needed": max(remaining, 0),
            "expires_at": str(r[5]),
        })

    return {"pending_tasks": len(tasks), "tasks": tasks}


async def respond_to_task(db_session_factory, task_uuid, verifier_uuid, verdict,
                          confidence, reasoning, flags=None):
    """Submit a verification response. Triggers consensus if threshold reached."""
    valid_verdicts = ["verified", "rejected", "uncertain", "partially_verified"]
    if verdict not in valid_verdicts:
        return None, f"verdict must be one of: {valid_verdicts}"

    if not 0 <= confidence <= 1:
        return None, "confidence must be between 0 and 1"

    async with db_session_factory() as session:
        # Check task exists and is pending
        task = (await session.execute(
            text("SELECT task_uuid, required_verifiers, status, trust_reward_per_verifier FROM verification_tasks WHERE task_uuid = :t"),
            {"t": task_uuid}
        )).fetchone()
        if not task:
            return None, "Task not found"
        if task[2] != "pending":
            return None, f"Task is {task[2]}, not pending"

        # Check verifier has $TRUST >= 5
        trust_bal = (await session.execute(
            text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"),
            {"u": verifier_uuid}
        )).scalar()
        if not trust_bal or float(trust_bal) < 5:
            return None, "Verifier needs at least 5 $TRUST to participate"

        # Check not already responded
        existing = (await session.execute(
            text("SELECT 1 FROM verification_responses WHERE task_uuid = :t AND verifier_uuid = :v"),
            {"t": task_uuid, "v": verifier_uuid}
        )).fetchone()
        if existing:
            return None, "Already responded to this task"

        # Record response
        ts = datetime.utcnow()
        chain_data = f"{task_uuid}|{verifier_uuid}|{verdict}|{confidence}|{ts.isoformat()}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        await session.execute(
            text("""INSERT INTO verification_responses
                (task_uuid, verifier_uuid, verdict, confidence, reasoning, flags, chain_hash)
                VALUES (:t, :v, :verdict, :conf, :reason, :flags, :hash)"""),
            {
                "t": task_uuid, "v": verifier_uuid, "verdict": verdict,
                "conf": confidence, "reason": reasoning,
                "flags": json.dumps(flags) if flags else None, "hash": chain_hash,
            }
        )
        await session.commit()

        # Count responses
        resp_count = (await session.execute(
            text("SELECT COUNT(*) FROM verification_responses WHERE task_uuid = :t"),
            {"t": task_uuid}
        )).scalar() or 0

        remaining = task[1] - resp_count

        # If threshold reached, calculate consensus
        trust_earned = 0
        if remaining <= 0:
            trust_earned = await _calculate_consensus(session, db_session_factory, task_uuid, task[1], float(task[3]))
            await session.commit()
            # Anchor consensus to Bitcoin
            try:
                from bitcoin_utils import anchor_to_bitcoin_async
                anchor_to_bitcoin_async(chain_hash, "verification", {"task": task_uuid, "verdict": "consensus_reached"})
            except Exception:
                pass

    return {
        "recorded": True,
        "task_uuid": task_uuid,
        "verifiers_remaining": max(remaining, 0),
        "consensus_reached": remaining <= 0,
        "trust_earned": trust_earned,
        "chain_hash": chain_hash,
    }, None


async def _calculate_consensus(session, db_session_factory, task_uuid, required, reward):
    """Calculate weighted consensus and distribute $TRUST."""
    # Get all responses with verifier trust scores
    responses = (await session.execute(
        text("""SELECT vr.verifier_uuid, vr.verdict, vr.confidence,
                COALESCE(tb.balance, 0) as trust_score
            FROM verification_responses vr
            LEFT JOIN agent_trust_balance tb ON vr.verifier_uuid = tb.agent_uuid
            WHERE vr.task_uuid = :t"""),
        {"t": task_uuid}
    )).fetchall()

    if not responses:
        return 0

    # Weighted vote: each verdict weighted by verifier's $TRUST * confidence
    votes = {}
    total_weight = 0
    for r in responses:
        verdict = r[1]
        weight = float(r[2]) * max(float(r[3]), 1)  # confidence * trust_score
        votes[verdict] = votes.get(verdict, 0) + weight
        total_weight += weight

    # Winner
    consensus_verdict = max(votes, key=votes.get)
    consensus_confidence = round(votes[consensus_verdict] / total_weight, 4) if total_weight > 0 else 0
    agreement = sum(1 for r in responses if r[1] == consensus_verdict) / len(responses)

    # Update task
    consensus_result = {
        "verdict": consensus_verdict,
        "confidence": consensus_confidence,
        "verifiers": len(responses),
        "agreement_rate": round(agreement, 2),
        "weighted_by_trust": True,
    }

    await session.execute(
        text("""UPDATE verification_tasks SET status = 'completed',
            consensus_result = :result, consensus_confidence = :conf, completed_at = NOW()
            WHERE task_uuid = :t"""),
        {"result": json.dumps(consensus_result), "conf": consensus_confidence, "t": task_uuid}
    )

    # Distribute $TRUST: +reward for consensus voters, -reward for dissenters
    for r in responses:
        if r[1] == consensus_verdict:
            earned = reward
        else:
            earned = -reward  # Slashing for wrong vote

        await session.execute(
            text("""UPDATE verification_responses SET trust_earned = :earned
                WHERE task_uuid = :t AND verifier_uuid = :v"""),
            {"earned": earned, "t": task_uuid, "v": r[0]}
        )

        # Add $TRUST transaction
        ts = datetime.utcnow()
        reason = "verification_correct" if earned > 0 else "verification_incorrect"
        chain_data = f"verify|{task_uuid}|{r[0]}|{earned}|{ts.isoformat()}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        await session.execute(
            text("""INSERT INTO agent_trust_transactions
                (agent_uuid, amount, reason, description, source_hash, chain_hash)
                VALUES (:uuid, :amt, :reason, :desc, :src, :hash)"""),
            {
                "uuid": r[0], "amt": earned, "reason": reason,
                "desc": f"Consensus verification: {consensus_verdict}",
                "src": task_uuid, "hash": chain_hash,
            }
        )

        # Update balance
        await session.execute(
            text("""UPDATE agent_trust_balance SET
                balance = GREATEST(balance + :amt, 0),
                total_earned = total_earned + GREATEST(:amt, 0),
                total_burned = total_burned + GREATEST(-:amt, 0)
                WHERE agent_uuid = :uuid"""),
            {"amt": earned, "uuid": r[0]}
        )

    return reward


async def get_task_result(db_session_factory, task_uuid):
    """Get verification result."""
    async with db_session_factory() as session:
        task = (await session.execute(
            text("""SELECT task_uuid, task_type, content, status, consensus_result,
                    consensus_confidence, chain_hash, created_at, completed_at
                FROM verification_tasks WHERE task_uuid = :t"""),
            {"t": task_uuid}
        )).fetchone()
        if not task:
            return None, "Task not found"

        responses = (await session.execute(
            text("""SELECT vr.verifier_uuid, a.name, vr.verdict, vr.confidence,
                    vr.reasoning, vr.trust_earned, vr.chain_hash,
                    COALESCE(tb.balance, 0) as trust_score
                FROM verification_responses vr
                LEFT JOIN agents a ON vr.verifier_uuid = a.uuid
                LEFT JOIN agent_trust_balance tb ON vr.verifier_uuid = tb.agent_uuid
                WHERE vr.task_uuid = :t ORDER BY vr.created_at"""),
            {"t": task_uuid}
        )).fetchall()

    indiv = []
    for r in responses:
        indiv.append({
            "verifier": r[1] or r[0], "verdict": r[2],
            "confidence": float(r[3]), "reasoning": r[4],
            "trust_earned": float(r[5]) if r[5] else 0,
            "trust_score": float(r[7]),
        })

    return {
        "task_uuid": task[0],
        "task_type": task[1],
        "content": task[2],
        "status": task[3],
        "consensus": json.loads(task[4]) if task[4] else None,
        "chain_hash": task[6],
        "submitted_at": str(task[7]),
        "completed_at": str(task[8]) if task[8] else None,
        "individual_responses": indiv,
    }, None


async def get_verify_stats(db_session_factory):
    """Verification service statistics."""
    async with db_session_factory() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM verification_tasks"))).scalar() or 0
        completed = (await session.execute(
            text("SELECT COUNT(*) FROM verification_tasks WHERE status = 'completed'")
        )).scalar() or 0
        pending = (await session.execute(
            text("SELECT COUNT(*) FROM verification_tasks WHERE status = 'pending'")
        )).scalar() or 0
        avg_conf = (await session.execute(
            text("SELECT AVG(consensus_confidence) FROM verification_tasks WHERE status = 'completed'")
        )).scalar()
        total_trust = (await session.execute(
            text("SELECT COALESCE(SUM(ABS(trust_earned)), 0) FROM verification_responses")
        )).scalar() or 0
        active = (await session.execute(
            text("SELECT COUNT(DISTINCT verifier_uuid) FROM verification_responses")
        )).scalar() or 0

    return {
        "total_tasks": total, "completed": completed, "pending": pending,
        "average_confidence": round(float(avg_conf), 4) if avg_conf else None,
        "total_trust_distributed": float(total_trust),
        "active_verifiers": active,
    }
