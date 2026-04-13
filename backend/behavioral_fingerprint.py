"""Behavioral Fingerprint — Longitudinal agent behavior tracking"""
import hashlib
import json
import statistics
from datetime import datetime, date, timedelta
from sqlalchemy import text


async def compute_fingerprint(db_session_factory, agent_uuid):
    """Compute behavioral fingerprint for an agent based on vault events and heartbeats."""
    async with db_session_factory() as session:
        # Verify agent exists
        agent = (await session.execute(
            text("SELECT uuid, name, trust_score, created_at FROM agents WHERE uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        # Get vault events for heartbeat regularity
        events = (await session.execute(
            text("""SELECT created_at FROM agent_vault_events
                WHERE agent_uuid = :u ORDER BY created_at"""),
            {"u": agent_uuid}
        )).fetchall()

        # Compute heartbeat regularity (consistency of intervals)
        regularity = 0.0
        intervals = []
        if len(events) >= 2:
            for i in range(1, len(events)):
                diff = (events[i][0] - events[i - 1][0]).total_seconds()
                if diff > 0:
                    intervals.append(diff)
            if intervals:
                mean_interval = statistics.mean(intervals)
                if mean_interval > 0 and len(intervals) > 1:
                    stdev = statistics.stdev(intervals)
                    regularity = round(max(0, 1 - (stdev / mean_interval)), 4)
                elif mean_interval > 0:
                    regularity = 1.0

        # Total events
        total_events = len(events)

        # Activity pattern: events per hour bucket
        hour_buckets = [0] * 24
        for e in events:
            hour_buckets[e[0].hour] += 1
        active_hours = sum(1 for h in hour_buckets if h > 0)

        # Compute drift from baseline (compare current week vs first week)
        drift = 0.0
        if total_events > 0:
            first_event = events[0][0]
            midpoint = first_event + timedelta(days=3)
            early = sum(1 for e in events if e[0] < midpoint)
            late = sum(1 for e in events if e[0] >= midpoint)
            if early > 0:
                drift = round(abs(late - early) / max(early, late), 4)

        # Get scan history count
        scan_count = (await session.execute(
            text("SELECT COUNT(*) FROM agent_scan_history WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).scalar() or 0

        # Get previous fingerprint for comparison
        prev = (await session.execute(
            text("""SELECT heartbeat_regularity, drift_from_baseline, fingerprint_hash
                FROM agent_behavioral_fingerprint WHERE agent_uuid = :u
                ORDER BY fingerprint_date DESC LIMIT 1"""),
            {"u": agent_uuid}
        )).fetchone()

        # Create fingerprint hash
        today = date.today()
        fp_data = f"{agent_uuid}|{regularity}|{total_events}|{today}"
        fingerprint_hash = hashlib.sha256(fp_data.encode()).hexdigest()

        # Save fingerprint
        await session.execute(
            text("""INSERT INTO agent_behavioral_fingerprint
                (agent_uuid, fingerprint_date, heartbeat_regularity, drift_from_baseline,
                 fingerprint_hash, activity_pattern)
                VALUES (:uuid, :date, :reg, :drift, :hash, :pattern)"""),
            {
                "uuid": agent_uuid, "date": today, "reg": regularity, "drift": drift,
                "hash": fingerprint_hash,
                "pattern": json.dumps({"total_events": total_events, "active_hours": active_hours,
                                       "hour_distribution": hour_buckets}),
            }
        )
        await session.commit()

    # Compute stability (how much fingerprint changed from previous)
    stability = None
    if prev:
        prev_reg = float(prev[0] or 0)
        prev_drift = float(prev[1] or 0)
        reg_change = abs(regularity - prev_reg)
        drift_change = abs(drift - prev_drift)
        stability = round(1 - ((reg_change + drift_change) / 2), 4)

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "fingerprint_date": str(today),
        "fingerprint_hash": fingerprint_hash,
        "heartbeat_regularity": regularity,
        "drift_from_baseline": drift,
        "total_events": total_events,
        "active_hours": active_hours,
        "scan_history_count": scan_count,
        "stability_vs_previous": stability,
        "previous_fingerprint": prev[2] if prev else None,
    }, None


async def get_fingerprint_history(db_session_factory, agent_uuid):
    """Get historical fingerprints for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT fingerprint_date, heartbeat_regularity, drift_from_baseline,
                    fingerprint_hash, activity_pattern, created_at
                FROM agent_behavioral_fingerprint WHERE agent_uuid = :u
                ORDER BY fingerprint_date DESC LIMIT 30"""),
            {"u": agent_uuid}
        )).fetchall()

    history = []
    for r in rows:
        history.append({
            "date": str(r[0]),
            "regularity": float(r[1]) if r[1] else 0,
            "drift": float(r[2]) if r[2] else 0,
            "fingerprint_hash": r[3],
            "activity": json.loads(r[4]) if r[4] else None,
        })

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "fingerprints": history,
        "total_snapshots": len(history),
    }, None


async def save_scan_snapshot(db_session_factory, agent_uuid):
    """Save current security scan as a historical snapshot."""
    async with db_session_factory() as session:
        score = (await session.execute(
            text("""SELECT overall_score, identity_score, endpoint_score,
                    behavior_score, network_score, code_score
                FROM agent_security_score WHERE agent_uuid = :u"""),
            {"u": agent_uuid}
        )).fetchone()
        if not score:
            return None

        rating = "A" if score[0] >= 80 else "B" if score[0] >= 60 else "C" if score[0] >= 40 else "D" if score[0] >= 20 else "F"
        today = date.today()

        await session.execute(
            text("""INSERT INTO agent_scan_history
                (agent_uuid, scan_date, overall_score, identity_score, endpoint_score,
                 behavior_score, network_score, code_score, rating)
                VALUES (:uuid, :date, :overall, :identity, :endpoint, :behavior, :network, :code, :rating)"""),
            {
                "uuid": agent_uuid, "date": today,
                "overall": score[0], "identity": score[1], "endpoint": score[2],
                "behavior": score[3], "network": score[4], "code": score[5],
                "rating": rating,
            }
        )
        await session.commit()
        return {"saved": True, "date": str(today), "rating": rating, "score": float(score[0])}


async def get_scan_history(db_session_factory, agent_uuid):
    """Get scan history for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT scan_date, overall_score, rating, identity_score, endpoint_score,
                    behavior_score, network_score, code_score
                FROM agent_scan_history WHERE agent_uuid = :u
                ORDER BY scan_date DESC LIMIT 30"""),
            {"u": agent_uuid}
        )).fetchall()

    scans = []
    for r in rows:
        scans.append({
            "date": str(r[0]), "overall": float(r[1]), "rating": r[2],
            "identity": float(r[3]) if r[3] else None,
            "endpoint": float(r[4]) if r[4] else None,
            "behavior": float(r[5]) if r[5] else None,
            "network": float(r[6]) if r[6] else None,
            "code": float(r[7]) if r[7] else None,
        })

    # Compute trend
    trend = None
    if len(scans) >= 2:
        latest = scans[0]["overall"]
        oldest = scans[-1]["overall"]
        trend = "improving" if latest > oldest else "declining" if latest < oldest else "stable"

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "scans": scans,
        "total_scans": len(scans),
        "trend": trend,
    }, None
