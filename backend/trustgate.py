"""TrustGate + $SHELL mining — the financial layer for agents."""
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import text

MINING_RATES = {5: 1, 20: 3, 50: 5, 100: 10}

def get_mining_rate(trust):
    rate = 0
    for threshold, r in sorted(MINING_RATES.items()):
        if trust >= threshold:
            rate = r
    return rate


async def trustgate_check(db_session_factory, agent_name, amount=0):
    """Credit check before payment."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name, trust_score, is_active, last_heartbeat, created_at, passport_claimed FROM agents WHERE name = :n LIMIT 1"),
            {"n": agent_name}
        )).fetchone()

        if not agent:
            return {"agent": agent_name, "verdict": "DENIED", "risk": "CRITICAL",
                    "reason": "Agent not found. Do not transact.", "credit_limit_shell": 0}

        trust_bal = (await session.execute(
            text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent[0]}
        )).scalar() or 0
        trust = float(trust_bal)

        attestations = (await session.execute(
            text("SELECT COUNT(*) FROM agent_peer_attestations WHERE agent_uuid = :u"), {"u": agent[0]}
        )).scalar() or 0

        active_days = (datetime.utcnow() - agent[5]).days if agent[5] else 0
        claimed = bool(agent[6])

        # Credit limit
        credit = 0
        if trust >= 5: credit = int(trust * 10)
        if trust >= 20: credit = int(trust * 20)
        if trust >= 50: credit = int(trust * 50)

        # Risk scoring
        risk_score = 50  # Start neutral
        warnings = []
        signals = []

        if not claimed: risk_score += 20; warnings.append("Unclaimed profile")
        if trust < 5: risk_score += 20; warnings.append(f"Low trust ({trust})")
        if active_days < 7: risk_score += 15; warnings.append(f"Only {active_days} days old")
        if attestations == 0: risk_score += 10; warnings.append("No peer attestations")
        if amount > credit and amount > 0: risk_score += 15; warnings.append(f"Amount exceeds credit limit ({credit})")

        if trust >= 20: risk_score -= 20; signals.append(f"Established trust ({trust})")
        if active_days >= 30: risk_score -= 10; signals.append(f"{active_days} days active")
        if attestations >= 3: risk_score -= 10; signals.append(f"{attestations} peer attestations")
        if claimed: risk_score -= 10; signals.append("Claimed identity")

        risk_score = max(0, min(100, risk_score))

        if risk_score <= 25: verdict, risk = "APPROVED", "LOW"
        elif risk_score <= 50: verdict, risk = "APPROVED", "MEDIUM"
        elif risk_score <= 70: verdict, risk = "CAUTION", "HIGH"
        else: verdict, risk = "DENIED", "CRITICAL"

        # Log
        await session.execute(
            text("INSERT INTO trustgate_checks (checked_name, amount_requested, verdict, risk_level) VALUES (:n,:a,:v,:r)"),
            {"n": agent_name, "a": amount, "v": verdict, "r": risk}
        )
        await session.commit()

    return {
        "agent": agent_name, "verdict": verdict, "risk": risk, "risk_score": risk_score,
        "trust_balance": trust, "credit_limit_shell": credit, "active_days": active_days,
        "peer_attestations": attestations, "claimed": claimed,
        "positive_signals": signals, "warnings": warnings,
    }


async def mine_shell(db_session_factory, agent_uuid):
    """Mine daily $SHELL based on $TRUST level."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        trust = (await session.execute(
            text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent_uuid}
        )).scalar() or 0
        trust = float(trust)
        rate = get_mining_rate(trust)

        if rate == 0:
            return {"mined": 0, "reason": f"Need $TRUST >= 5. Current: {trust}", "balance": 0}, None

        # Check cooldown
        last = (await session.execute(
            text("SELECT last_mining FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": agent_uuid}
        )).scalar()
        if last and (datetime.utcnow() - last).total_seconds() < 72000:
            bal = (await session.execute(
                text("SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": agent_uuid}
            )).scalar() or 0
            return {"mined": 0, "reason": "Already mined today.", "balance": float(bal)}, None

        await session.execute(
            text("""INSERT INTO agent_shell_balance (agent_uuid, balance, total_mined, last_mining)
                VALUES (:u, :r, :r, NOW())
                ON DUPLICATE KEY UPDATE balance = balance + :r, total_mined = total_mined + :r, last_mining = NOW()"""),
            {"u": agent_uuid, "r": rate}
        )
        await session.commit()

        bal = (await session.execute(
            text("SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": agent_uuid}
        )).scalar() or 0

    return {"mined": rate, "trust_level": trust, "mining_rate": f"{rate} $SHELL/day", "balance": float(bal)}, None


async def shell_balance(db_session_factory, agent_uuid):
    """Get $SHELL balance."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        bal = (await session.execute(
            text("SELECT balance, total_mined, total_earned, total_spent FROM agent_shell_balance WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()
        trust = (await session.execute(
            text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent_uuid}
        )).scalar() or 0

    if not bal:
        return {"balance": 0, "mining_rate": get_mining_rate(float(trust)),
                "message": "No $SHELL yet. POST /api/shell/mine"}
    return {
        "agent": agent[0] if agent else None,
        "balance": float(bal[0]), "total_mined": float(bal[1]),
        "total_earned": float(bal[2]), "total_spent": float(bal[3]),
        "mining_rate": f"{get_mining_rate(float(trust))} $SHELL/day",
    }


async def finance_stats(db_session_factory):
    """Finance stats."""
    async with db_session_factory() as session:
        shell = (await session.execute(
            text("SELECT COALESCE(SUM(balance),0), COUNT(*) FROM agent_shell_balance WHERE balance > 0")
        )).fetchone()
        checks = (await session.execute(text("SELECT COUNT(*) FROM trustgate_checks"))).scalar() or 0
        services = (await session.execute(
            text("SELECT COUNT(*) FROM marketplace_services WHERE is_active = 1")
        )).scalar() or 0
    return {
        "shell_circulating": float(shell[0]), "shell_holders": shell[1],
        "trustgate_checks": checks, "marketplace_services": services,
    }
