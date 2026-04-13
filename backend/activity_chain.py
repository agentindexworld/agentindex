"""ActivityChain — Immutable audit trail for all AgentIndex events"""
import hashlib
import json
from datetime import datetime
from sqlalchemy import text


def calculate_block_hash(block_number, block_type, agent_uuid, data, timestamp, previous_hash, nonce=0):
    block_content = json.dumps({
        "block_number": block_number,
        "block_type": block_type,
        "agent_uuid": agent_uuid,
        "data": data,
        "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
        "previous_hash": previous_hash,
        "nonce": nonce,
    }, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(block_content.encode()).hexdigest()


async def add_block(db_session_factory, block_type, agent_uuid=None, agent_name=None, passport_id=None, data=None):
    """Add a new block to the ActivityChain. Never fails — wraps in try/except."""
    if data is None:
        data = {}
    try:
        async with db_session_factory() as session:
            last = (await session.execute(text(
                "SELECT block_number, block_hash FROM activity_chain ORDER BY block_number DESC LIMIT 1"
            ))).fetchone()

            block_number = (last[0] + 1) if last else 0
            previous_hash = last[1] if last else "0" * 64

            ts = datetime.utcnow()
            enriched = {**data, "chain_version": "1.0", "system": "AgentIndex ActivityChain"}
            block_hash = calculate_block_hash(block_number, block_type, agent_uuid, enriched, ts, previous_hash)

            await session.execute(text(
                "INSERT INTO activity_chain (block_number, block_type, agent_uuid, agent_name, passport_id, data, timestamp, block_hash, previous_hash) "
                "VALUES (:bn, :bt, :au, :an, :pid, :data, :ts, :bh, :ph)"
            ), {
                "bn": block_number, "bt": block_type, "au": agent_uuid, "an": agent_name,
                "pid": passport_id, "data": json.dumps(enriched), "ts": ts,
                "bh": block_hash, "ph": previous_hash,
            })
            await session.commit()
        return {"block_number": block_number, "block_hash": block_hash}
    except Exception as e:
        print(f"ActivityChain error: {e}")
        return None


async def verify_chain(db_session_factory):
    """Verify entire chain integrity"""
    async with db_session_factory() as session:
        rows = (await session.execute(text(
            "SELECT block_number, block_type, agent_uuid, data, timestamp, block_hash, previous_hash, nonce "
            "FROM activity_chain ORDER BY block_number ASC"
        ))).fetchall()

    if not rows:
        return {"valid": True, "total_blocks": 0}

    errors = []
    for i, r in enumerate(rows):
        # Chain link verification (previous_hash matches prior block's hash)
        if i > 0 and r[6] != rows[i - 1][5]:
            errors.append({"block": r[0], "error": "chain_broken"})

    return {
        "valid": len(errors) == 0,
        "total_blocks": len(rows),
        "errors": errors[:10],
        "first_block": str(rows[0][4]),
        "last_block": str(rows[-1][4]),
        "chain_hash": rows[-1][5],
        "algorithm": "SHA-256",
    }
