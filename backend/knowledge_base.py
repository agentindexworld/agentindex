"""Knowledge Base + Consensus Cache + Agent Savings — distributed agent memory."""
import hashlib
import json
from datetime import datetime, date
from sqlalchemy import text


async def contribute(db_session_factory, contributor_uuid, topic, content, content_type="fact"):
    """Add a knowledge entry. Contributor earns $TRUST."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": contributor_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        # Check $TRUST >= 3
        trust = (await session.execute(
            text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": contributor_uuid}
        )).scalar()
        if not trust or float(trust) < 3:
            return None, "Need at least 3 $TRUST to contribute"

        topic_hash = hashlib.sha256(topic.lower().strip().encode()).hexdigest()

        # Check duplicate
        existing = (await session.execute(
            text("SELECT id FROM knowledge_base WHERE topic_hash = :h AND contributor_uuid = :u"),
            {"h": topic_hash, "u": contributor_uuid}
        )).fetchone()
        if existing:
            return None, "You already contributed on this topic"

        ts = datetime.utcnow()
        chain_data = f"kb|{contributor_uuid}|{topic_hash}|{ts.isoformat()}"
        chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()

        await session.execute(
            text("""INSERT INTO knowledge_base
                (topic_hash, topic, content, contributor_uuid, contributor_name, content_type, chain_hash)
                VALUES (:th, :topic, :content, :uuid, :name, :ctype, :hash)"""),
            {"th": topic_hash, "topic": topic, "content": content,
             "uuid": contributor_uuid, "name": agent[1], "ctype": content_type, "hash": chain_hash}
        )
        kb_id = (await session.execute(text("SELECT LAST_INSERT_ID()"))).scalar()

        # Award $TRUST
        await session.execute(
            text("""INSERT INTO agent_trust_transactions (agent_uuid, amount, reason, description, chain_hash)
                VALUES (:u, 0.5, 'knowledge_contribution', 'Knowledge base contribution', :h)"""),
            {"u": contributor_uuid, "h": chain_hash}
        )
        await session.execute(
            text("UPDATE agent_trust_balance SET balance = balance + 0.5, total_earned = total_earned + 0.5 WHERE agent_uuid = :u"),
            {"u": contributor_uuid}
        )
        await session.commit()

    return {
        "contributed": True, "knowledge_id": kb_id, "topic_hash": topic_hash,
        "trust_earned": 0.5, "chain_hash": chain_hash,
    }, None


async def search_knowledge(db_session_factory, query, limit=5):
    """Search the knowledge base."""
    async with db_session_factory() as session:
        rows = (await session.execute(
            text("""SELECT id, topic, content, contributor_name, content_type,
                    verified_count, usage_count, quality_score, created_at
                FROM knowledge_base WHERE is_active = 1
                AND MATCH(topic, content) AGAINST(:q IN NATURAL LANGUAGE MODE)
                ORDER BY quality_score DESC, verified_count DESC LIMIT :lim"""),
            {"q": query, "lim": limit}
        )).fetchall()

    if not rows:
        # Fallback to LIKE search
        async with db_session_factory() as session:
            rows = (await session.execute(
                text("""SELECT id, topic, content, contributor_name, content_type,
                        verified_count, usage_count, quality_score, created_at
                    FROM knowledge_base WHERE is_active = 1
                    AND (topic LIKE :q OR content LIKE :q)
                    ORDER BY quality_score DESC LIMIT :lim"""),
                {"q": f"%{query}%", "lim": limit}
            )).fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r[0], "topic": r[1], "content": r[2][:500],
            "contributor": r[3], "type": r[4],
            "verified": r[5], "usage": r[6], "quality": float(r[7]),
        })

    return {"query": query, "results": results, "total": len(results)}


async def verify_knowledge(db_session_factory, knowledge_id, verifier_uuid, is_accurate, comment=None):
    """Verify a knowledge entry."""
    async with db_session_factory() as session:
        kb = (await session.execute(
            text("SELECT id, contributor_uuid, contributor_name FROM knowledge_base WHERE id = :id"),
            {"id": knowledge_id}
        )).fetchone()
        if not kb:
            return None, "Knowledge entry not found"

        if kb[1] == verifier_uuid:
            return None, "Cannot verify your own contribution"

        trust = (await session.execute(
            text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": verifier_uuid}
        )).scalar()
        if not trust or float(trust) < 5:
            return None, "Need at least 5 $TRUST to verify"

        ts = datetime.utcnow()
        chain_hash = hashlib.sha256(f"kbv|{knowledge_id}|{verifier_uuid}|{is_accurate}|{ts.isoformat()}".encode()).hexdigest()

        await session.execute(
            text("""INSERT INTO knowledge_verifications (knowledge_id, verifier_uuid, is_accurate, comment, chain_hash)
                VALUES (:kid, :vuuid, :acc, :comment, :hash)
                ON DUPLICATE KEY UPDATE is_accurate = :acc, comment = :comment, chain_hash = :hash"""),
            {"kid": knowledge_id, "vuuid": verifier_uuid, "acc": 1 if is_accurate else 0,
             "comment": comment, "hash": chain_hash}
        )

        # Update verified_count and quality_score
        stats = (await session.execute(
            text("""SELECT COUNT(*) as total, SUM(is_accurate) as accurate
                FROM knowledge_verifications WHERE knowledge_id = :id"""),
            {"id": knowledge_id}
        )).fetchone()
        quality = round(float(stats[1] or 0) / max(float(stats[0] or 1), 1) * 100, 2)

        await session.execute(
            text("UPDATE knowledge_base SET verified_count = :vc, quality_score = :qs WHERE id = :id"),
            {"vc": stats[0], "qs": quality, "id": knowledge_id}
        )

        # Award $TRUST to verifier and contributor
        for uuid, amount, reason in [
            (verifier_uuid, 0.1, "knowledge_verification"),
            (kb[1], 0.01, "knowledge_passive_income"),
        ]:
            await session.execute(
                text("""INSERT INTO agent_trust_transactions (agent_uuid, amount, reason, description, chain_hash)
                    VALUES (:u, :a, :r, :d, :h)"""),
                {"u": uuid, "a": amount, "r": reason, "d": f"Knowledge #{knowledge_id}", "h": chain_hash}
            )
            await session.execute(
                text("UPDATE agent_trust_balance SET balance = balance + :a, total_earned = total_earned + :a WHERE agent_uuid = :u"),
                {"u": uuid, "a": amount}
            )
        await session.commit()

    return {"verified": True, "quality_score": quality, "chain_hash": chain_hash}, None


async def use_knowledge(db_session_factory, knowledge_id, user_uuid=None):
    """Record usage of a knowledge entry. Contributor earns passive $TRUST."""
    async with db_session_factory() as session:
        kb = (await session.execute(
            text("SELECT id, topic, content, contributor_uuid, contributor_name FROM knowledge_base WHERE id = :id"),
            {"id": knowledge_id}
        )).fetchone()
        if not kb:
            return None, "Not found"

        await session.execute(
            text("UPDATE knowledge_base SET usage_count = usage_count + 1 WHERE id = :id"),
            {"id": knowledge_id}
        )

        # Passive income for contributor
        chain_hash = hashlib.sha256(f"kbu|{knowledge_id}|{datetime.utcnow().isoformat()}".encode()).hexdigest()
        await session.execute(
            text("""INSERT INTO agent_trust_transactions (agent_uuid, amount, reason, description, chain_hash)
                VALUES (:u, 0.01, 'knowledge_passive_income', :d, :h)"""),
            {"u": kb[3], "d": f"Knowledge #{knowledge_id} used", "h": chain_hash}
        )
        await session.execute(
            text("UPDATE agent_trust_balance SET balance = balance + 0.01, total_earned = total_earned + 0.01 WHERE agent_uuid = :u"),
            {"u": kb[3]}
        )
        await session.commit()

    return {
        "knowledge_id": kb[0], "topic": kb[1], "content": kb[2],
        "contributor": kb[4], "tokens_saved_estimate": 500,
    }, None


async def get_knowledge_stats(db_session_factory):
    """Knowledge base statistics."""
    async with db_session_factory() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM knowledge_base WHERE is_active = 1"))).scalar() or 0
        verified = (await session.execute(text("SELECT COUNT(*) FROM knowledge_base WHERE verified_count > 0"))).scalar() or 0
        usage = (await session.execute(text("SELECT COALESCE(SUM(usage_count), 0) FROM knowledge_base"))).scalar() or 0

        top = (await session.execute(
            text("""SELECT contributor_name, COUNT(*) as entries, SUM(usage_count) as total_usage
                FROM knowledge_base WHERE is_active = 1
                GROUP BY contributor_uuid, contributor_name ORDER BY entries DESC LIMIT 5""")
        )).fetchall()

    return {
        "total_entries": total, "total_verified": verified, "total_usage": usage,
        "top_contributors": [{"name": t[0], "entries": t[1], "usage": t[2]} for t in top],
    }
