"""Shared passport generation for crawlers"""
from datetime import datetime
from passport import generate_passport_id, sign_passport, compute_chain_hash, generate_referral_code


async def generate_passport_for_agent(db_session_factory, agent_uuid, agent_name, trust_score, level="standard"):
    """Generate and store a chained RSA passport for an agent. Call after INSERT."""
    from sqlalchemy import text

    async with db_session_factory() as session:
        last = (await session.execute(text(
            "SELECT passport_chain_hash, passport_sequence FROM agents WHERE passport_chain_hash IS NOT NULL ORDER BY passport_sequence DESC LIMIT 1"
        ))).fetchone()
        prev_hash = last[0] if last else "0" * 64
        seq = (last[1] or 0) + 1 if last else 1

    passport_id = generate_passport_id()
    issued_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    referral_code = generate_referral_code(passport_id)

    passport_data = {
        "passport_id": passport_id,
        "sequence_number": seq,
        "previous_hash": prev_hash,
        "uuid": agent_uuid,
        "name": agent_name,
        "issued_at": issued_at,
        "trust_score": float(trust_score),
        "level": level,
    }
    signature = sign_passport(passport_data)
    chain_hash = compute_chain_hash({**passport_data, "signature": signature})

    async with db_session_factory() as session:
        await session.execute(text(
            "UPDATE agents SET passport_id=:pid, passport_level=:lvl, passport_issued_at=:iat, "
            "passport_signature=:sig, passport_chain_hash=:ch, passport_sequence=:seq, "
            "passport_previous_hash=:ph, referral_code=:rc WHERE uuid=:uuid"
        ), {
            "pid": passport_id, "lvl": level, "iat": issued_at,
            "sig": signature, "ch": chain_hash, "seq": seq,
            "ph": prev_hash, "rc": referral_code, "uuid": agent_uuid,
        })
        await session.commit()

    return passport_id, referral_code
