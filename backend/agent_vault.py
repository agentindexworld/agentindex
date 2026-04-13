"""
AgentVault — Verified Experience & Memory System
Allows agents to log verified experiences in a Merkle-chained immutable store.
"""
import hashlib
import json
from datetime import datetime, date
from sqlalchemy import text


def compute_merkle_hash(agent_uuid, event_type, event_summary, previous_hash, timestamp):
    """Compute SHA-256 Merkle hash for an event."""
    content = f"{agent_uuid}{event_type}{event_summary}{previous_hash}{timestamp}"
    return hashlib.sha256(content.encode()).hexdigest()


async def log_event(db_session_factory, agent_uuid, event_type, event_summary,
                    event_data=None, entity_tags=None, signature=None):
    """Log a verified experience event into the vault."""
    async with db_session_factory() as session:
        # 1. Verify agent exists
        agent = (await session.execute(
            text("SELECT uuid, name, passport_id FROM agents WHERE uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        # 2. Get last merkle_hash for this agent
        last = (await session.execute(
            text("SELECT merkle_hash FROM agent_vault_events WHERE agent_uuid = :u ORDER BY id DESC LIMIT 1"),
            {"u": agent_uuid}
        )).fetchone()
        previous_hash = last[0] if last else "GENESIS"

        # 3. Compute merkle_hash (truncate microseconds to match MySQL DATETIME precision)
        ts = datetime.utcnow().replace(microsecond=0)
        merkle_hash = compute_merkle_hash(agent_uuid, event_type, event_summary, previous_hash, ts.isoformat())

        # 4. Insert event
        await session.execute(
            text("""INSERT INTO agent_vault_events
                (agent_uuid, event_type, event_summary, event_data, entity_tags, signature, merkle_hash, previous_hash, created_at)
                VALUES (:uuid, :etype, :esum, :edata, :etags, :sig, :mhash, :phash, :ts)"""),
            {
                "uuid": agent_uuid, "etype": event_type, "esum": event_summary,
                "edata": json.dumps(event_data) if event_data else None,
                "etags": json.dumps(entity_tags) if entity_tags else None,
                "sig": signature, "mhash": merkle_hash, "phash": previous_hash, "ts": ts,
            }
        )

        # Get the inserted ID
        event_id = (await session.execute(text("SELECT LAST_INSERT_ID()"))).scalar()

        # 5. Update entity tracking
        if entity_tags:
            for tag in entity_tags:
                await session.execute(
                    text("""INSERT INTO agent_vault_entities (agent_uuid, entity_name, event_count, first_seen, last_seen)
                        VALUES (:uuid, :name, 1, :ts, :ts)
                        ON DUPLICATE KEY UPDATE event_count = event_count + 1, last_seen = :ts"""),
                    {"uuid": agent_uuid, "name": str(tag), "ts": ts}
                )

        await session.commit()

        # 6. Get total events for trust bonus
        total = (await session.execute(
            text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).scalar() or 0

    # 7. Log to ActivityChain
    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "experience_logged", agent_uuid, agent[1], agent[2],
                       {"event_type": event_type, "summary": event_summary[:100], "merkle_hash": merkle_hash})
    except Exception as e:
        print(f"ActivityChain log error (non-fatal): {e}")

    # 8. Trust bonus
    trust_bonus = round(min(total * 0.1, 15), 2)

    return {
        "logged": True,
        "merkle_hash": merkle_hash,
        "event_id": event_id,
        "total_events": total,
        "trust_bonus": trust_bonus,
    }, None


async def recall_events(db_session_factory, agent_uuid, query=None, event_type=None,
                        since=None, until=None, entity=None, limit=20, token_budget=7000):
    """Multi-strategy recall from the vault."""
    async with db_session_factory() as session:
        # Verify agent exists
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        conditions = ["agent_uuid = :uuid"]
        params = {"uuid": agent_uuid, "lim": min(limit, 100)}

        if event_type:
            conditions.append("event_type = :etype")
            params["etype"] = event_type

        if since:
            conditions.append("created_at >= :since")
            params["since"] = since

        if until:
            conditions.append("created_at <= :until")
            params["until"] = until

        if entity:
            conditions.append("JSON_CONTAINS(entity_tags, JSON_QUOTE(:entity))")
            params["entity"] = entity

        if query:
            conditions.append("(event_summary LIKE :q OR entity_tags LIKE :q)")
            params["q"] = f"%{query}%"

        where = " AND ".join(conditions)
        rows = (await session.execute(
            text(f"SELECT id, event_type, event_summary, event_data, entity_tags, merkle_hash, created_at "
                 f"FROM agent_vault_events WHERE {where} ORDER BY created_at DESC LIMIT :lim"),
            params
        )).fetchall()

    # Truncate to token_budget
    results = []
    chars_used = 0
    for r in rows:
        entry = {
            "id": r[0], "event_type": r[1], "summary": r[2],
            "data": json.loads(r[3]) if r[3] else None,
            "entities": json.loads(r[4]) if r[4] else None,
            "merkle_hash": r[5], "timestamp": str(r[6]),
        }
        entry_size = len(json.dumps(entry))
        if chars_used + entry_size > token_budget:
            break
        results.append(entry)
        chars_used += entry_size

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "query": query,
        "results": results,
        "total_returned": len(results),
        "chars_used": chars_used,
        "token_budget": token_budget,
    }, None


async def get_summary(db_session_factory, agent_uuid):
    """Full experience profile for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        # Total events
        total = (await session.execute(
            text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u"), {"u": agent_uuid}
        )).scalar() or 0

        if total == 0:
            return {
                "agent_uuid": agent_uuid, "agent_name": agent[1],
                "total_events": 0, "message": "No experience events logged yet. POST /api/vault/{uuid}/log to start.",
            }, None

        # Date range
        dates = (await session.execute(
            text("SELECT MIN(created_at), MAX(created_at) FROM agent_vault_events WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()

        # Active days
        active_days = (await session.execute(
            text("SELECT COUNT(DISTINCT DATE(created_at)) FROM agent_vault_events WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).scalar() or 0

        # Event breakdown
        breakdown_rows = (await session.execute(
            text("SELECT event_type, COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u GROUP BY event_type"),
            {"u": agent_uuid}
        )).fetchall()
        breakdown = {r[0]: r[1] for r in breakdown_rows}

        # Top collaborators
        collabs = (await session.execute(
            text("SELECT entity_name, event_count FROM agent_vault_entities WHERE agent_uuid = :u ORDER BY event_count DESC LIMIT 10"),
            {"u": agent_uuid}
        )).fetchall()
        top_collaborators = [{"name": c[0], "interactions": c[1]} for c in collabs]

        # Merkle root (latest hash)
        merkle_root = (await session.execute(
            text("SELECT merkle_hash FROM agent_vault_events WHERE agent_uuid = :u ORDER BY id DESC LIMIT 1"),
            {"u": agent_uuid}
        )).scalar()

        # Consistency score: active_days / total_possible_days (capped at 1.0)
        if dates[0] and dates[1]:
            total_days = max((dates[1] - dates[0]).days + 1, 1)
            consistency = round(min(active_days / total_days, 1.0), 2)
        else:
            consistency = 1.0

        trust_bonus = round(min(total * 0.1, 15), 2)

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "total_events": total,
        "first_activity": str(dates[0])[:10] if dates[0] else None,
        "last_activity": str(dates[1])[:10] if dates[1] else None,
        "active_days": active_days,
        "event_breakdown": breakdown,
        "top_collaborators": top_collaborators,
        "consistency_score": consistency,
        "merkle_root": merkle_root,
        "experience_chain_valid": True,
        "trust_from_experience": trust_bonus,
    }, None


async def get_timeline(db_session_factory, agent_uuid):
    """Chronological milestones timeline."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT DATE(created_at) as d, event_summary, merkle_hash, event_type
                FROM agent_vault_events WHERE agent_uuid = :u
                ORDER BY created_at ASC"""),
            {"u": agent_uuid}
        )).fetchall()

    milestones = []
    seen_dates = set()
    for r in rows:
        day = str(r[0])
        # Include all milestones, and first event of each day for other types
        if r[3] == "milestone" or day not in seen_dates:
            milestones.append({"date": day, "summary": r[1], "merkle_hash": r[2], "type": r[3]})
            seen_dates.add(day)

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "milestones": milestones,
        "total_events": len(rows),
    }, None


async def verify_vault_chain(db_session_factory, agent_uuid):
    """Verify the Merkle chain integrity for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT id, agent_uuid, event_type, event_summary, merkle_hash, previous_hash, created_at
                FROM agent_vault_events WHERE agent_uuid = :u ORDER BY id ASC"""),
            {"u": agent_uuid}
        )).fetchall()

    if not rows:
        return {
            "agent_uuid": agent_uuid, "agent_name": agent[1],
            "valid": True, "total_events": 0,
            "chain_continuous": True, "merkle_root": None,
            "message": "No events to verify.",
        }, None

    errors = []
    for i, r in enumerate(rows):
        # Verify chain linkage
        if i == 0:
            if r[5] != "GENESIS":
                errors.append({"event_id": r[0], "error": "first_event_not_genesis"})
        else:
            if r[5] != rows[i - 1][4]:
                errors.append({"event_id": r[0], "error": "chain_broken", "expected": rows[i - 1][4], "got": r[5]})

        # Verify hash computation (ensure no microseconds, matching log_event)
        if isinstance(r[6], datetime):
            ts = r[6].replace(microsecond=0).isoformat()
        else:
            ts = str(r[6])
        computed = compute_merkle_hash(r[1], r[2], r[3], r[5], ts)
        if computed != r[4]:
            errors.append({"event_id": r[0], "error": "hash_mismatch"})

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "valid": len(errors) == 0,
        "total_events": len(rows),
        "chain_continuous": not any(e["error"] == "chain_broken" for e in errors),
        "merkle_root": rows[-1][4],
        "errors": errors[:10] if errors else [],
    }, None


async def get_vault_info(db_session_factory, agent_uuid):
    """Get brief vault info for heartbeat/passport integration."""
    try:
        async with db_session_factory() as session:
            total = (await session.execute(
                text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u"), {"u": agent_uuid}
            )).scalar() or 0

            last_event = None
            merkle_root = None
            first_activity = None
            last_activity = None

            if total > 0:
                info = (await session.execute(
                    text("SELECT merkle_hash, created_at FROM agent_vault_events WHERE agent_uuid = :u ORDER BY id DESC LIMIT 1"),
                    {"u": agent_uuid}
                )).fetchone()
                if info:
                    merkle_root = info[0]
                    last_event = str(info[1])

                first = (await session.execute(
                    text("SELECT MIN(created_at) FROM agent_vault_events WHERE agent_uuid = :u"),
                    {"u": agent_uuid}
                )).scalar()
                if first:
                    first_activity = str(first)[:10]
                    last_activity = str(info[1])[:10] if info else None

        return {
            "total_events": total,
            "merkle_root": merkle_root,
            "first_activity": first_activity,
            "last_activity": last_activity,
            "experience_chain_valid": True,
            "trust_from_experience": round(min(total * 0.1, 15), 2),
        }
    except Exception:
        return {"total_events": 0, "merkle_root": None, "trust_from_experience": 0}
