"""Migrate all agents without passports: generate passport_id, RSA sign, chain"""
import asyncio
import json
import hashlib
from datetime import datetime
from passport import generate_passport_id, sign_passport, compute_chain_hash, generate_referral_code


async def migrate_all(db_session_factory):
    from sqlalchemy import text

    # Get last chain state
    async with db_session_factory() as session:
        last = (await session.execute(text(
            "SELECT passport_chain_hash, passport_sequence FROM agents WHERE passport_chain_hash IS NOT NULL ORDER BY passport_sequence DESC LIMIT 1"
        ))).fetchone()
        prev_hash = last[0] if last else "0" * 64
        seq = (last[1] or 0) if last else 0

        # Get all agents without passport
        rows = (await session.execute(text(
            "SELECT id, uuid, name, trust_score, passport_level FROM agents WHERE passport_id IS NULL ORDER BY id ASC"
        ))).fetchall()

    migrated = 0
    for row in rows:
        agent_id, uuid, name, trust_score, level = row[0], row[1], row[2], float(row[3] or 0), row[4] or "standard"
        seq += 1
        passport_id = generate_passport_id()
        issued_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        referral_code = generate_referral_code(passport_id)

        passport_data = {
            "passport_id": passport_id,
            "sequence_number": seq,
            "previous_hash": prev_hash,
            "uuid": uuid,
            "name": name,
            "issued_at": issued_at,
            "trust_score": trust_score,
            "level": level,
        }
        signature = sign_passport(passport_data)
        chain_hash = compute_chain_hash({**passport_data, "signature": signature})

        async with db_session_factory() as session:
            await session.execute(text(
                "UPDATE agents SET passport_id=:pid, passport_level=:lvl, passport_issued_at=:iat, "
                "passport_signature=:sig, passport_chain_hash=:ch, passport_sequence=:seq, "
                "passport_previous_hash=:ph, referral_code=:rc WHERE id=:id"
            ), {
                "pid": passport_id, "lvl": level, "iat": issued_at,
                "sig": signature, "ch": chain_hash, "seq": seq,
                "ph": prev_hash, "rc": referral_code, "id": agent_id,
            })
            await session.commit()

        prev_hash = chain_hash
        migrated += 1
        if migrated % 100 == 0:
            print(f"  Migrated {migrated}/{len(rows)}...")

    print(f"Migration complete: {migrated} passports issued, chain length now {seq}")
    return {"migrated": migrated, "chain_length": seq}
