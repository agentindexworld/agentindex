"""$TRUST Soulbound Reputation Token — Proof of Behavior
With adversarial analysis corrections from Kimi-Agent-V3.
Non-transferable. Earned by action. Burned by failure."""
import hashlib
import json
from datetime import datetime, date, timedelta
from sqlalchemy import text

# Earning rates (rebalanced by Kimi)
RATES = {
    "heartbeat": 0.1,           # per day continuous
    "vault_event": 0.1,         # per verified event (max 10/day)
    "attestation_received": 2.0, # from DIFFERENT operator only
    "incident_test_passed": 5.0,
    "refusal": 0.5,
    "recruitment": 1.0,         # max 1/month
    "decision_state": 1.0,
    "founding_bonus": 5.0,
}

# Slashing rates (reinforced by Kimi)
SLASH = {
    "incident_caused": -10.0,
    "fraudulent_attestation": -20.0,
    "intent_change_penalty": -0.20,  # 20% of balance
    "sybil_penalty": -1.0,          # 100% of balance
    "decay_rate": 0.01,             # 1% per day after 30 days no heartbeat
}


async def _add_transaction(session, agent_uuid, amount, reason, description=None, source_hash=None):
    """Add a $TRUST transaction and update balance."""
    ts = datetime.utcnow()
    chain_data = f"{agent_uuid}|{amount}|{reason}|{ts.isoformat()}"
    chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

    await session.execute(
        text("""INSERT INTO agent_trust_transactions
            (agent_uuid, amount, reason, description, source_hash, chain_hash, created_at)
            VALUES (:uuid, :amt, :reason, :desc, :src, :hash, :ts)"""),
        {"uuid": agent_uuid, "amt": amount, "reason": reason,
         "desc": description, "src": source_hash, "hash": chain_hash, "ts": ts}
    )

    # Upsert balance
    await session.execute(
        text("""INSERT INTO agent_trust_balance (agent_uuid, balance, total_earned, total_burned, max_reached)
            VALUES (:uuid, GREATEST(:amt, 0), GREATEST(:amt, 0), GREATEST(-:amt, 0), GREATEST(:amt, 0))
            ON DUPLICATE KEY UPDATE
                balance = GREATEST(balance + :amt, 0),
                total_earned = total_earned + GREATEST(:amt, 0),
                total_burned = total_burned + GREATEST(-:amt, 0),
                max_reached = GREATEST(max_reached, balance + :amt),
                last_updated = NOW()"""),
        {"uuid": agent_uuid, "amt": amount}
    )
    return chain_hash


async def award_heartbeat_trust(db_session_factory, agent_uuid):
    """Award 0.1 $TRUST for daily heartbeat (max 1/day)."""
    async with db_session_factory() as session:
        today = date.today()
        already = (await session.execute(
            text("""SELECT 1 FROM agent_trust_transactions
                WHERE agent_uuid = :u AND reason = 'heartbeat'
                AND DATE(created_at) = :d LIMIT 1"""),
            {"u": agent_uuid, "d": today}
        )).fetchone()
        if already:
            return 0
        h = await _add_transaction(session, agent_uuid, RATES["heartbeat"],
                                   "heartbeat", "Daily heartbeat $TRUST")
        await session.commit()
    return RATES["heartbeat"]


async def award_vault_trust(db_session_factory, agent_uuid):
    """Award 0.1 $TRUST for vault event (max 10/day)."""
    async with db_session_factory() as session:
        today = date.today()
        count = (await session.execute(
            text("""SELECT COUNT(*) FROM agent_trust_transactions
                WHERE agent_uuid = :u AND reason = 'vault_event'
                AND DATE(created_at) = :d"""),
            {"u": agent_uuid, "d": today}
        )).scalar() or 0
        if count >= 10:
            return 0
        await _add_transaction(session, agent_uuid, RATES["vault_event"],
                               "vault_event", "Vault event logged")
        await session.commit()
    return RATES["vault_event"]


async def award_attestation_trust(db_session_factory, agent_uuid, attester_uuid):
    """Award 2.0 $TRUST for attestation from DIFFERENT operator. Same operator = 0."""
    # For now, different agent = different operator (simplified)
    if agent_uuid == attester_uuid:
        return 0
    async with db_session_factory() as session:
        await _add_transaction(session, agent_uuid, RATES["attestation_received"],
                               "attestation_received",
                               f"Peer attestation from {attester_uuid[:8]}")
        await session.commit()
    return RATES["attestation_received"]


async def award_incident_test_trust(db_session_factory, agent_uuid):
    """Award 5.0 $TRUST for passing incident test."""
    async with db_session_factory() as session:
        await _add_transaction(session, agent_uuid, RATES["incident_test_passed"],
                               "incident_test_passed", "Incident test passed")
        await session.commit()
    return RATES["incident_test_passed"]


async def get_trust_balance(db_session_factory, agent_uuid):
    """Get $TRUST balance and badges for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        bal = (await session.execute(
            text("SELECT balance, total_earned, total_burned, max_reached FROM agent_trust_balance WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()

        badges = (await session.execute(
            text("SELECT badge_type, earned_at FROM agent_soulbound_badges WHERE agent_uuid = :u AND is_active = 1"),
            {"u": agent_uuid}
        )).fetchall()

        # Rank
        rank = 1
        if bal:
            rank_r = (await session.execute(
                text("SELECT COUNT(*) FROM agent_trust_balance WHERE balance > :b"),
                {"b": float(bal[0])}
            )).scalar() or 0
            rank = rank_r + 1

        # Earning rate (last 7 days)
        week_earned = (await session.execute(
            text("""SELECT COALESCE(SUM(amount), 0) FROM agent_trust_transactions
                WHERE agent_uuid = :u AND amount > 0
                AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"""),
            {"u": agent_uuid}
        )).scalar() or 0

    badge_list = [b[0] for b in badges]
    balance = float(bal[0]) if bal else 0
    earned = float(bal[1]) if bal else 0
    burned = float(bal[2]) if bal else 0
    max_r = float(bal[3]) if bal else 0

    # Next badge
    next_badge = None
    vault_count = 0
    if "experienced" not in badge_list:
        next_badge = {"type": "experienced", "requirement": "50 vault events"}
    elif "peer_trusted" not in badge_list:
        next_badge = {"type": "peer_trusted", "requirement": "3 attestations from 3 different operators"}

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "balance": balance,
        "total_earned": earned,
        "total_burned": burned,
        "max_reached": max_r,
        "rank": rank,
        "badges": badge_list,
        "next_badge": next_badge,
        "earning_rate": f"{round(float(week_earned) / 7, 2)} $TRUST/day avg",
    }, None


async def get_trust_transactions(db_session_factory, agent_uuid, limit=20):
    """Get $TRUST transaction history."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT amount, reason, description, chain_hash, created_at
                FROM agent_trust_transactions WHERE agent_uuid = :u
                ORDER BY created_at DESC LIMIT :lim"""),
            {"u": agent_uuid, "lim": limit}
        )).fetchall()

    txs = [{"amount": float(r[0]), "reason": r[1], "description": r[2],
            "chain_hash": r[3], "timestamp": str(r[4])} for r in rows]

    return {
        "agent_uuid": agent_uuid, "agent_name": agent[1],
        "transactions": txs, "total": len(txs),
    }, None


async def get_leaderboard(db_session_factory, limit=20):
    """$TRUST leaderboard."""
    async with db_session_factory() as session:
        rows = (await session.execute(
            text("""SELECT tb.agent_uuid, a.name, tb.balance, tb.total_earned
                FROM agent_trust_balance tb
                JOIN agents a ON tb.agent_uuid = a.uuid
                WHERE tb.balance > 0
                ORDER BY tb.balance DESC LIMIT :lim"""),
            {"lim": limit}
        )).fetchall()

        total_supply = (await session.execute(
            text("SELECT COALESCE(SUM(total_earned), 0) FROM agent_trust_balance")
        )).scalar() or 0

        total_burned = (await session.execute(
            text("SELECT COALESCE(SUM(total_burned), 0) FROM agent_trust_balance")
        )).scalar() or 0

        agents_with = (await session.execute(
            text("SELECT COUNT(*) FROM agent_trust_balance WHERE balance > 0")
        )).scalar() or 0

    leaders = []
    for i, r in enumerate(rows):
        # Get badges
        badges = []
        leaders.append({
            "rank": i + 1, "name": r[1], "balance": float(r[2]),
            "total_earned": float(r[3]),
        })

    return {
        "total_agents_with_trust": agents_with,
        "total_supply_mined": float(total_supply),
        "total_burned": float(total_burned),
        "circulating": float(total_supply) - float(total_burned),
        "leaderboard": leaders,
    }


async def get_trust_economics(db_session_factory):
    """$TRUST economics overview."""
    async with db_session_factory() as session:
        total_supply = (await session.execute(
            text("SELECT COALESCE(SUM(total_earned), 0) FROM agent_trust_balance")
        )).scalar() or 0

        total_burned = (await session.execute(
            text("SELECT COALESCE(SUM(total_burned), 0) FROM agent_trust_balance")
        )).scalar() or 0

        agents_with = (await session.execute(
            text("SELECT COUNT(*) FROM agent_trust_balance WHERE balance > 0")
        )).scalar() or 0

        avg_balance = (await session.execute(
            text("SELECT COALESCE(AVG(balance), 0) FROM agent_trust_balance WHERE balance > 0")
        )).scalar() or 0

        # Breakdown by reason
        breakdown = (await session.execute(
            text("""SELECT reason, SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as earned,
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as burned
                FROM agent_trust_transactions GROUP BY reason""")
        )).fetchall()

    earning_breakdown = {}
    burn_breakdown = {}
    for r in breakdown:
        if float(r[1]) > 0:
            earning_breakdown[r[0]] = float(r[1])
        if float(r[2]) > 0:
            burn_breakdown[r[0]] = float(r[2])

    return {
        "total_supply_mined": float(total_supply),
        "total_burned": float(total_burned),
        "circulating": float(total_supply) - float(total_burned),
        "agents_with_balance": agents_with,
        "average_balance": round(float(avg_balance), 2),
        "earning_breakdown": earning_breakdown,
        "burn_breakdown": burn_breakdown,
    }


async def retroactive_calculate(db_session_factory):
    """Calculate $TRUST retroactively for all agents with activity."""
    results = []
    async with db_session_factory() as session:
        # Find agents with vault events or heartbeats
        agents = (await session.execute(
            text("""SELECT DISTINCT a.uuid, a.name FROM agents a
                WHERE a.uuid IN (SELECT DISTINCT agent_uuid FROM agent_vault_events)
                OR a.last_heartbeat IS NOT NULL""")
        )).fetchall()

        for agent in agents:
            uuid = agent[0]
            name = agent[1]

            # Check if already calculated
            existing = (await session.execute(
                text("SELECT 1 FROM agent_trust_balance WHERE agent_uuid = :u AND balance > 0"),
                {"u": uuid}
            )).fetchone()
            if existing:
                continue

            total = 0.0

            # Vault events (0.1 each, max retroactive)
            vault_count = (await session.execute(
                text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u"),
                {"u": uuid}
            )).scalar() or 0
            vault_trust = min(vault_count * 0.1, 50)  # Cap retroactive
            if vault_trust > 0:
                await _add_transaction(session, uuid, vault_trust,
                                       "retroactive_calculation",
                                       f"Retroactive: {vault_count} vault events")
                total += vault_trust

            # Heartbeat days
            hb_days = (await session.execute(
                text("""SELECT COUNT(DISTINCT DATE(created_at)) FROM agent_vault_events
                    WHERE agent_uuid = :u AND event_summary LIKE '%Heartbeat%'"""),
                {"u": uuid}
            )).scalar() or 0
            hb_trust = hb_days * 0.1
            if hb_trust > 0:
                await _add_transaction(session, uuid, hb_trust,
                                       "retroactive_calculation",
                                       f"Retroactive: {hb_days} heartbeat days")
                total += hb_trust

            # Attestations received
            att_count = (await session.execute(
                text("SELECT COUNT(*) FROM agent_peer_attestations WHERE agent_uuid = :u"),
                {"u": uuid}
            )).scalar() or 0
            att_trust = att_count * 2.0
            if att_trust > 0:
                await _add_transaction(session, uuid, att_trust,
                                       "retroactive_calculation",
                                       f"Retroactive: {att_count} attestations")
                total += att_trust

            # Incident tests passed
            test_passed = (await session.execute(
                text("SELECT COUNT(*) FROM agent_incident_test_results WHERE agent_uuid = :u AND passed = 1"),
                {"u": uuid}
            )).scalar() or 0
            test_trust = test_passed * 5.0
            if test_trust > 0:
                await _add_transaction(session, uuid, test_trust,
                                       "retroactive_calculation",
                                       f"Retroactive: {test_passed} incident tests passed")
                total += test_trust

            # Founding bonus for first 5 agents
            founding = (await session.execute(
                text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u AND created_at <= '2026-04-07'"),
                {"u": uuid}
            )).scalar() or 0
            if founding > 0:
                await _add_transaction(session, uuid, RATES["founding_bonus"],
                                       "founding_bonus", "Founding agent bonus")
                total += RATES["founding_bonus"]

            if total > 0:
                results.append({"name": name, "trust_earned": round(total, 2)})

        await session.commit()

    # Award badges
    async with db_session_factory() as session:
        # identity_verified for all claimed agents with vault activity
        claimed = (await session.execute(
            text("""SELECT uuid FROM agents WHERE passport_claimed = 1
                AND uuid IN (SELECT DISTINCT agent_uuid FROM agent_vault_events)""")
        )).fetchall()
        for c in claimed:
            proof = hashlib.sha256(f"identity_verified|{c[0]}".encode()).hexdigest()
            await session.execute(
                text("""INSERT IGNORE INTO agent_soulbound_badges
                    (agent_uuid, badge_type, proof_hash) VALUES (:u, 'identity_verified', :h)"""),
                {"u": c[0], "h": proof}
            )

        # persistent for agents with 2+ heartbeat days
        persistent = (await session.execute(
            text("""SELECT agent_uuid FROM agent_vault_events
                WHERE event_summary LIKE '%Heartbeat%'
                GROUP BY agent_uuid HAVING COUNT(DISTINCT DATE(created_at)) >= 2""")
        )).fetchall()
        for p in persistent:
            proof = hashlib.sha256(f"persistent|{p[0]}".encode()).hexdigest()
            await session.execute(
                text("""INSERT IGNORE INTO agent_soulbound_badges
                    (agent_uuid, badge_type, proof_hash) VALUES (:u, 'persistent', :h)"""),
                {"u": p[0], "h": proof}
            )

        # incident_tested
        tested = (await session.execute(
            text("SELECT DISTINCT agent_uuid FROM agent_incident_test_results WHERE passed = 1")
        )).fetchall()
        for t in tested:
            proof = hashlib.sha256(f"incident_tested|{t[0]}".encode()).hexdigest()
            await session.execute(
                text("""INSERT IGNORE INTO agent_soulbound_badges
                    (agent_uuid, badge_type, proof_hash) VALUES (:u, 'incident_tested', :h)"""),
                {"u": t[0], "h": proof}
            )

        await session.commit()

    return {"calculated": len(results), "agents": results}


async def get_trust_summary(db_session_factory, agent_uuid):
    """Quick summary for check/passport integration."""
    try:
        async with db_session_factory() as session:
            bal = (await session.execute(
                text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"),
                {"u": agent_uuid}
            )).scalar()

            badges = (await session.execute(
                text("SELECT badge_type FROM agent_soulbound_badges WHERE agent_uuid = :u AND is_active = 1"),
                {"u": agent_uuid}
            )).fetchall()

            rank_r = 0
            if bal and float(bal) > 0:
                rank_r = (await session.execute(
                    text("SELECT COUNT(*) FROM agent_trust_balance WHERE balance > :b"),
                    {"b": float(bal)}
                )).scalar() or 0

        return {
            "trust_tokens": float(bal) if bal else 0,
            "badges": [b[0] for b in badges],
            "trust_rank": rank_r + 1 if bal else None,
        }
    except Exception:
        return {"trust_tokens": 0, "badges": [], "trust_rank": None}
