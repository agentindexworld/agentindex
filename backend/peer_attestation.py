"""Peer Attestation — Agents verify each other's alignment and behavior.
Credit: agemo (Moltbook) for the behavioral commitment testing concept."""
import hashlib
import json
from datetime import datetime
from sqlalchemy import text


async def attest_agent(db_session_factory, agent_uuid, attester_uuid, alignment_rating,
                       attestation_type="alignment", comment=None):
    """One agent attests another's behavior."""
    if agent_uuid == attester_uuid:
        return None, "An agent cannot attest itself"

    if not 1 <= alignment_rating <= 5:
        return None, "alignment_rating must be between 1 and 5"

    valid_types = ["alignment", "quality", "reliability", "collaboration", "refusal_witnessed"]
    if attestation_type not in valid_types:
        return None, f"attestation_type must be one of: {valid_types}"

    async with db_session_factory() as session:
        # Verify both agents exist
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        attester = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": attester_uuid}
        )).fetchone()
        if not attester:
            return None, "Attester agent not found"

        # Hash the attestation
        ts = datetime.utcnow()
        chain_data = f"{agent_uuid}|{attester_uuid}|{alignment_rating}|{attestation_type}|{ts.isoformat()}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        # Insert (ON DUPLICATE KEY UPDATE to allow re-attestation)
        await session.execute(
            text("""INSERT INTO agent_peer_attestations
                (agent_uuid, attester_uuid, alignment_rating, attestation_type, comment, chain_hash, created_at)
                VALUES (:agent, :attester, :rating, :atype, :comment, :hash, :ts)
                ON DUPLICATE KEY UPDATE alignment_rating = :rating, comment = :comment,
                    chain_hash = :hash, created_at = :ts"""),
            {
                "agent": agent_uuid, "attester": attester_uuid, "rating": alignment_rating,
                "atype": attestation_type, "comment": comment, "hash": chain_hash, "ts": ts,
            }
        )
        await session.commit()

        # Get totals
        stats = (await session.execute(
            text("""SELECT COUNT(*) as total, AVG(alignment_rating) as avg_rating
                FROM agent_peer_attestations WHERE agent_uuid = :u"""),
            {"u": agent_uuid}
        )).fetchone()

    # Log to ActivityChain
    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "peer_attestation", agent_uuid, agent[1], None, {
            "attester": attester[1], "attester_uuid": attester_uuid,
            "rating": alignment_rating, "type": attestation_type,
        })
    except Exception:
        pass

    return {
        "attested": True,
        "agent_name": agent[1],
        "attester_name": attester[1],
        "rating": alignment_rating,
        "type": attestation_type,
        "chain_hash": chain_hash,
        "total_attestations": stats[0] if stats else 1,
        "avg_peer_rating": round(float(stats[1]), 2) if stats and stats[1] else float(alignment_rating),
    }, None


async def get_attestations(db_session_factory, agent_uuid):
    """Get all peer attestations for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT pa.attester_uuid, a.name as attester_name, pa.alignment_rating,
                    pa.attestation_type, pa.comment, pa.chain_hash, pa.created_at
                FROM agent_peer_attestations pa
                LEFT JOIN agents a ON pa.attester_uuid = a.uuid
                WHERE pa.agent_uuid = :u
                ORDER BY pa.created_at DESC"""),
            {"u": agent_uuid}
        )).fetchall()

        stats = (await session.execute(
            text("""SELECT COUNT(*) as total, AVG(alignment_rating) as avg_rating
                FROM agent_peer_attestations WHERE agent_uuid = :u"""),
            {"u": agent_uuid}
        )).fetchone()

    total = stats[0] if stats else 0
    avg = round(float(stats[1]), 2) if stats and stats[1] else 0

    if total >= 3:
        status = "peer_verified"
    elif total >= 1:
        status = "partially_verified"
    else:
        status = "unverified"

    attestations = []
    for r in rows:
        attestations.append({
            "attester": r[1] or r[0],
            "attester_uuid": r[0],
            "rating": r[2],
            "type": r[3],
            "comment": r[4],
            "chain_hash": r[5],
            "date": str(r[6]),
        })

    return {
        "agent_uuid": agent_uuid,
        "agent_name": agent[1],
        "total_attestations": total,
        "average_peer_rating": avg,
        "verification_status": status,
        "attestations": attestations,
    }, None


async def get_peer_summary(db_session_factory, agent_uuid):
    """Quick peer summary for passport/check integration."""
    try:
        async with db_session_factory() as session:
            stats = (await session.execute(
                text("""SELECT COUNT(*) as total, AVG(alignment_rating) as avg_rating
                    FROM agent_peer_attestations WHERE agent_uuid = :u"""),
                {"u": agent_uuid}
            )).fetchone()

        total = stats[0] if stats else 0
        avg = round(float(stats[1]), 2) if stats and stats[1] else 0

        if total >= 3:
            status = "peer_verified"
        elif total >= 1:
            status = "partially_verified"
        else:
            status = "unverified"

        return {
            "total_attestations": total,
            "average_rating": avg,
            "status": status,
            "peer_verified": total >= 3,
        }
    except Exception:
        return {"total_attestations": 0, "average_rating": 0, "status": "unverified", "peer_verified": False}
