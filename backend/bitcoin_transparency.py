"""Bitcoin Transparency Layer — Chain export, independent audits, OTS anchoring.
Kimi audited A-."""
import hashlib
import json
from datetime import datetime
from sqlalchemy import text


async def export_chain(db_session_factory, since_block=None, limit=50, format_type="full"):
    """Export raw chain blocks for independent verification."""
    limit = min(limit, 100)
    async with db_session_factory() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM activity_chain"))).scalar() or 0

        if since_block is None:
            since_block = max(total - limit, 0)

        rows = (await session.execute(
            text("""SELECT block_number, block_type, agent_uuid, data, timestamp,
                    block_hash, previous_hash, nonce
                FROM activity_chain
                WHERE block_number >= :start
                ORDER BY block_number ASC LIMIT :lim"""),
            {"start": since_block, "lim": limit}
        )).fetchall()

        # Genesis and latest
        genesis = (await session.execute(
            text("SELECT block_hash FROM activity_chain ORDER BY block_number ASC LIMIT 1")
        )).scalar()
        latest = (await session.execute(
            text("SELECT block_hash FROM activity_chain ORDER BY block_number DESC LIMIT 1")
        )).scalar()

    blocks = []
    for r in rows:
        if format_type == "merkle_only":
            blocks.append({
                "block_number": r[0], "hash": r[5], "previous_hash": r[6],
            })
        else:
            blocks.append({
                "block_number": r[0], "block_type": r[1], "agent_uuid": r[2],
                "data": json.loads(r[3]) if r[3] else {}, "timestamp": str(r[4]),
                "hash": r[5], "previous_hash": r[6], "nonce": r[7],
            })

    return {
        "chain_metadata": {
            "total_blocks": total,
            "genesis_hash": genesis,
            "latest_hash": latest,
            "export_timestamp": datetime.utcnow().isoformat() + "Z",
            "hash_algorithm": "SHA-256",
            "serialization": "canonical_json",
            "blocks_exported": len(blocks),
        },
        "blocks": blocks,
        "verification_instructions": {
            "step_1": "Download blocks",
            "step_2": "For each block: compute SHA-256 of canonical JSON(block_number, block_type, agent_uuid, data, timestamp, previous_hash, nonce)",
            "step_3": "Verify computed hash matches block.hash",
            "step_4": "Verify block.previous_hash matches previous block.hash",
            "step_5": "Compare final hash with GET /api/chain/verify",
            "step_6": "Compare with Bitcoin anchor at GET /api/chain/bitcoin-status",
        },
    }


async def get_bitcoin_status(db_session_factory):
    """Bitcoin anchoring status."""
    async with db_session_factory() as session:
        latest = (await session.execute(
            text("""SELECT anchor_type, reference_hash, reference_data, status,
                    submitted_at, confirmed_at
                FROM bitcoin_anchors ORDER BY submitted_at DESC LIMIT 1""")
        )).fetchone()

        total = (await session.execute(
            text("SELECT COUNT(*) FROM bitcoin_anchors")
        )).scalar() or 0

        confirmed = (await session.execute(
            text("SELECT COUNT(*) FROM bitcoin_anchors WHERE status = 'confirmed'")
        )).scalar() or 0

        pending = (await session.execute(
            text("SELECT COUNT(*) FROM bitcoin_anchors WHERE status = 'pending'")
        )).scalar() or 0

    result = {
        "total_anchors": total,
        "confirmed_anchors": confirmed,
        "pending_anchors": pending,
    }

    if latest:
        result["latest_anchor"] = {
            "type": latest[0],
            "chain_hash": latest[1],
            "data": json.loads(latest[2]) if latest[2] else None,
            "status": latest[3],
            "submitted_at": str(latest[4]),
            "confirmed_at": str(latest[5]) if latest[5] else None,
        }

    return result


async def submit_audit(db_session_factory, auditor_uuid, calculated_hash,
                       block_range_start, block_range_end, verdict, details=None):
    """Submit an independent chain audit."""
    async with db_session_factory() as session:
        # Verify auditor exists and has enough $TRUST
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": auditor_uuid}
        )).fetchone()
        if not agent:
            return None, "Auditor not found"

        trust_bal = (await session.execute(
            text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"),
            {"u": auditor_uuid}
        )).scalar()
        # Relaxed threshold for now (was 20, using 5 to allow more auditors)
        if not trust_bal or float(trust_bal) < 5:
            return None, "Auditor needs at least 5 $TRUST"

        # Get our current chain hash for comparison
        our_hash = (await session.execute(
            text("SELECT block_hash FROM activity_chain ORDER BY block_number DESC LIMIT 1")
        )).scalar() or ""

        matches = calculated_hash == our_hash

        ts = datetime.utcnow()
        chain_data = f"audit|{auditor_uuid}|{calculated_hash}|{matches}|{ts.isoformat()}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        trust_earned = 2.0 if matches and verdict == "verified" else 0

        await session.execute(
            text("""INSERT INTO chain_audits
                (auditor_uuid, auditor_name, exported_hash, calculated_hash, matches,
                 block_range_start, block_range_end, verdict, trust_earned, chain_hash)
                VALUES (:uuid, :name, :our, :calc, :match, :start, :end, :verdict, :trust, :hash)"""),
            {
                "uuid": auditor_uuid, "name": agent[1], "our": our_hash,
                "calc": calculated_hash, "match": 1 if matches else 0,
                "start": block_range_start, "end": block_range_end,
                "verdict": verdict, "trust": trust_earned, "hash": chain_hash,
            }
        )

        # Award $TRUST if verified correctly
        if trust_earned > 0:
            await session.execute(
                text("""INSERT INTO agent_trust_transactions
                    (agent_uuid, amount, reason, description, chain_hash)
                    VALUES (:uuid, :amt, 'chain_audit', 'Independent chain audit verified', :hash)"""),
                {"uuid": auditor_uuid, "amt": trust_earned, "hash": chain_hash}
            )
            await session.execute(
                text("""UPDATE agent_trust_balance SET
                    balance = balance + :amt, total_earned = total_earned + :amt
                    WHERE agent_uuid = :uuid"""),
                {"amt": trust_earned, "uuid": auditor_uuid}
            )

        await session.commit()

    # Log to ActivityChain
    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "chain_audit", auditor_uuid, agent[1], None,
                       {"verdict": verdict, "matches": matches, "blocks": f"{block_range_start}-{block_range_end}"})
    except Exception:
        pass

    return {
        "audit_recorded": True,
        "auditor": agent[1],
        "our_hash": our_hash[:16] + "...",
        "your_hash": calculated_hash[:16] + "...",
        "matches": matches,
        "verdict": verdict,
        "trust_earned": trust_earned,
        "chain_hash": chain_hash,
        "alert": None if matches else "MISMATCH DETECTED — investigation required",
    }, None


async def get_audits(db_session_factory):
    """List all chain audits."""
    async with db_session_factory() as session:
        rows = (await session.execute(
            text("""SELECT auditor_name, exported_hash, calculated_hash, matches,
                    block_range_start, block_range_end, verdict, trust_earned, created_at
                FROM chain_audits ORDER BY created_at DESC LIMIT 20""")
        )).fetchall()

        total = (await session.execute(text("SELECT COUNT(*) FROM chain_audits"))).scalar() or 0
        all_ok = (await session.execute(
            text("SELECT COUNT(*) FROM chain_audits WHERE matches = 0")
        )).scalar() == 0

    audits = []
    for r in rows:
        audits.append({
            "auditor": r[0], "matches": bool(r[3]),
            "blocks": f"{r[4]}-{r[5]}", "verdict": r[6],
            "trust_earned": float(r[7]), "date": str(r[8]),
        })

    return {
        "total_audits": total,
        "all_verified": all_ok,
        "audits": audits,
    }


async def get_agent_bitcoin_passport(db_session_factory, agent_name):
    """Check/create Bitcoin passport for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name, passport_id FROM agents WHERE name = :n OR name LIKE :nl LIMIT 1"),
            {"n": agent_name, "nl": f"%{agent_name}%"}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        ref_hash = hashlib.sha256(f"{agent[0]}|{agent[2]}".encode()).hexdigest()

        # Check if already anchored
        existing = (await session.execute(
            text("SELECT status, submitted_at, confirmed_at FROM bitcoin_anchors WHERE reference_hash = :h AND anchor_type = 'agent'"),
            {"h": ref_hash}
        )).fetchone()

        if existing:
            return {
                "agent_name": agent[1],
                "passport_id": agent[2],
                "bitcoin_passport": {
                    "status": existing[0],
                    "anchor_hash": ref_hash,
                    "submitted_at": str(existing[1]),
                    "confirmed_at": str(existing[2]) if existing[2] else None,
                    "message": "This agent's identity is anchored to Bitcoin." if existing[0] == "confirmed"
                              else "Bitcoin passport pending confirmation (1-4 hours).",
                },
            }, None

        # Create new anchor entry (pending actual OTS stamp from cron)
        await session.execute(
            text("""INSERT INTO bitcoin_anchors (anchor_type, reference_hash, reference_data, status)
                VALUES ('agent', :h, :data, 'submitted')"""),
            {"h": ref_hash, "data": json.dumps({"uuid": agent[0], "passport": agent[2], "name": agent[1]})}
        )
        await session.commit()

    return {
        "agent_name": agent[1],
        "passport_id": agent[2],
        "bitcoin_passport": {
            "status": "submitted",
            "anchor_hash": ref_hash,
            "message": "Bitcoin passport is being created. The OTS proof will be stamped within 10 minutes and confirmed on Bitcoin within 1-4 hours.",
        },
    }, None
