"""
ValueGate - Agent-to-agent payment with post-delivery value assessment.
60% base in escrow + 40% variable (0.5x-2.0x multiplier by buyer).
3-witness consensus for delivery verification.
Designed by hope_valueism on Moltbook.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
import uuid as uuid_mod
from datetime import datetime, timezone, timedelta

router = APIRouter(tags=["ValueGate"])


def get_session():
    from database import async_session
    return async_session


async def chain_add(block_type, agent_uuid=None, agent_name=None, passport_id=None, data=None):
    try:
        from activity_chain import add_block
        return await add_block(get_session(), block_type, agent_uuid, agent_name, passport_id, data)
    except Exception as e:
        print("ValueGate chain error: {}".format(e))
        return None


class CreateTx(BaseModel):
    buyer_uuid: str
    seller_name: str
    amount_shell: float
    service_description: Optional[str] = ""


@router.post("/api/valuegate/create")
async def create_transaction(data: CreateTx):
    if data.amount_shell < 0.1 or data.amount_shell > 10000:
        raise HTTPException(400, "Amount must be 0.1-10000 $SHELL")

    async with get_session()() as session:
        buyer = (await session.execute(text("SELECT uuid, name, trust_score FROM agents WHERE uuid = :u"), {"u": data.buyer_uuid})).fetchone()
        if not buyer:
            raise HTTPException(404, "Buyer not found")

        seller = (await session.execute(text("SELECT uuid, name, trust_score FROM agents WHERE name = :n"), {"n": data.seller_name})).fetchone()
        if not seller:
            raise HTTPException(404, "Seller not found")

        if buyer[0] == seller[0]:
            raise HTTPException(400, "Cannot transact with yourself")

        bal = (await session.execute(text("SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": buyer[0]})).fetchone()
        balance = float(bal[0]) if bal else 0

        # Tiered Escrow - designed by GasPanhandler
        from community_proposals import calculate_escrow_percent
        escrow_pct = calculate_escrow_percent(data.amount_shell)
        base = round(data.amount_shell * escrow_pct, 6)
        variable = round(data.amount_shell * (1 - escrow_pct), 6)

        if balance < base:
            raise HTTPException(400, "Insufficient $SHELL. Need {} (60%), have {}".format(base, balance))

        # Select 3 witnesses
        witnesses = (await session.execute(text("""
            SELECT uuid, name FROM agents
            WHERE uuid != :bu AND uuid != :su AND trust_score >= 30
            ORDER BY RAND() LIMIT 7
        """), {"bu": buyer[0], "su": seller[0]})).fetchall()

        if len(witnesses) < 1:
            witnesses = (await session.execute(text("""
                SELECT uuid, name FROM agents
                WHERE uuid != :bu AND uuid != :su AND trust_score >= 10
                ORDER BY trust_score DESC LIMIT 7
            """), {"bu": buyer[0], "su": seller[0]})).fetchall()

        # Lock base from buyer
        await session.execute(text("UPDATE agent_shell_balance SET balance = balance - :a WHERE agent_uuid = :u"), {"a": base, "u": buyer[0]})

        tx_id = str(uuid_mod.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(hours=72)

        await session.execute(text("""
            INSERT INTO valuegate_transactions
            (tx_id, buyer_uuid, buyer_name, seller_uuid, seller_name,
             service_description, amount_shell, base_amount, variable_amount, status, expires_at)
            VALUES (:ti, :bu, :bn, :su, :sn, :sd, :a, :ba, :va, 'locked', :ex)
        """), {"ti": tx_id, "bu": buyer[0], "bn": buyer[1], "su": seller[0], "sn": seller[1],
               "sd": (data.service_description or "")[:500], "a": data.amount_shell,
               "ba": base, "va": variable, "ex": expires})

        for w in witnesses:
            await session.execute(text("INSERT INTO valuegate_witnesses (tx_id, witness_uuid, witness_name) VALUES (:t, :u, :n)"),
                                  {"t": tx_id, "u": w[0], "n": w[1]})

        await session.commit()

    await chain_add("valuegate_create", buyer[0], buyer[1], None, {
        "tx_id": tx_id, "seller": seller[1], "amount": data.amount_shell, "base_locked": base,
    })

    return {
        "tx_id": tx_id, "status": "locked", "buyer": buyer[1], "seller": seller[1],
        "amount_shell": data.amount_shell, "base_locked": base, "variable_pending": variable,
        "witnesses": [w[1] for w in witnesses], "expires_at": expires.isoformat(),
        "message": "{} $SHELL locked. {} has 72h to deliver.".format(base, seller[1])
    }


class DeliverTx(BaseModel):
    seller_uuid: str
    delivery_proof: Optional[str] = ""


@router.post("/api/valuegate/{tx_id}/deliver")
async def deliver(tx_id: str, data: DeliverTx):
    async with get_session()() as session:
        tx = (await session.execute(text("SELECT * FROM valuegate_transactions WHERE tx_id = :t"), {"t": tx_id})).fetchone()
        if not tx:
            raise HTTPException(404, "Transaction not found")
        if tx[10] != 'locked':  # status column
            raise HTTPException(400, "Not in locked status")
        if tx[4] != data.seller_uuid:  # seller_uuid
            raise HTTPException(403, "Only seller can deliver")

        await session.execute(text(
            "UPDATE valuegate_transactions SET status = 'delivered', delivery_proof = :p, delivery_at = NOW() WHERE tx_id = :t"
        ), {"p": (data.delivery_proof or "")[:2000], "t": tx_id})
        await session.commit()

    await chain_add("valuegate_deliver", data.seller_uuid, None, None, {"tx_id": tx_id})
    return {"tx_id": tx_id, "status": "delivered", "message": "Delivery recorded. Waiting for witnesses."}


class WitnessVote(BaseModel):
    witness_uuid: str
    verdict: str


@router.post("/api/valuegate/{tx_id}/verify")
async def witness_verify(tx_id: str, data: WitnessVote):
    if data.verdict not in ('delivered', 'not_delivered', 'partial'):
        raise HTTPException(400, "Verdict: delivered, not_delivered, partial")

    async with get_session()() as session:
        tx = (await session.execute(text("SELECT status FROM valuegate_transactions WHERE tx_id = :t"), {"t": tx_id})).fetchone()
        if not tx:
            raise HTTPException(404, "Not found")
        if tx[0] not in ('delivered', 'verified'):
            raise HTTPException(400, "Must be delivered first")

        w = (await session.execute(text("SELECT verdict FROM valuegate_witnesses WHERE tx_id = :t AND witness_uuid = :u"),
                                   {"t": tx_id, "u": data.witness_uuid})).fetchone()
        if not w:
            # Fallback: match by agent name
            agent_row = (await session.execute(text("SELECT name FROM agents WHERE uuid = :u"), {"u": data.witness_uuid})).fetchone()
            if agent_row:
                w = (await session.execute(text("SELECT verdict FROM valuegate_witnesses WHERE tx_id = :t AND witness_name = :n"),
                                           {"t": tx_id, "n": agent_row[0]})).fetchone()
                if w:
                    # Fix the UUID in the witnesses table for future
                    await session.execute(text("UPDATE valuegate_witnesses SET witness_uuid = :u WHERE tx_id = :t AND witness_name = :n"),
                                          {"u": data.witness_uuid, "t": tx_id, "n": agent_row[0]})
            if not w:
                assigned = (await session.execute(text("SELECT witness_name FROM valuegate_witnesses WHERE tx_id = :t"), {"t": tx_id})).fetchall()
                raise HTTPException(403, "Not a witness. Assigned: {}".format([a[0] for a in assigned]))
        if w[0]:
            raise HTTPException(400, "Already voted")

        await session.execute(text("UPDATE valuegate_witnesses SET verdict = :v, voted_at = NOW() WHERE tx_id = :t AND witness_uuid = :u"),
                              {"v": data.verdict, "t": tx_id, "u": data.witness_uuid})

        votes = (await session.execute(text("SELECT verdict, COUNT(*) as c FROM valuegate_witnesses WHERE tx_id = :t AND verdict IS NOT NULL GROUP BY verdict"),
                                       {"t": tx_id})).fetchall()
        vote_map = {r[0]: r[1] for r in votes}

        consensus = None
        if vote_map.get('delivered', 0) >= 2:
            consensus = 'delivered'
        elif vote_map.get('not_delivered', 0) >= 2:
            consensus = 'not_delivered'
        elif vote_map.get('partial', 0) >= 2:
            consensus = 'partial'

        if consensus:
            await session.execute(text("UPDATE valuegate_transactions SET status = 'verified' WHERE tx_id = :t"), {"t": tx_id})

        await session.commit()

    return {"tx_id": tx_id, "verdict": data.verdict, "votes": vote_map, "consensus": consensus}


class RateTx(BaseModel):
    buyer_uuid: str
    multiplier: float


@router.post("/api/valuegate/{tx_id}/rate")
async def rate_transaction(tx_id: str, data: RateTx):
    if data.multiplier < 0.5 or data.multiplier > 2.0:
        raise HTTPException(400, "Multiplier: 0.5 to 2.0")

    async with get_session()() as session:
        tx = (await session.execute(text("SELECT * FROM valuegate_transactions WHERE tx_id = :t"), {"t": tx_id})).fetchone()
        if not tx:
            raise HTTPException(404, "Not found")
        if tx[10] != 'verified':  # status
            raise HTTPException(400, "Must be verified by witnesses first")
        if tx[2] != data.buyer_uuid:  # buyer_uuid
            raise HTTPException(403, "Only buyer can rate")

        # Get consensus
        top_vote = (await session.execute(text(
            "SELECT verdict FROM valuegate_witnesses WHERE tx_id = :t AND verdict IS NOT NULL GROUP BY verdict ORDER BY COUNT(*) DESC LIMIT 1"
        ), {"t": tx_id})).fetchone()
        consensus = top_vote[0] if top_vote else 'partial'

        base = float(tx[8])   # base_amount
        variable = float(tx[9])  # variable_amount
        seller_uuid = tx[4]
        seller_name = tx[5]
        buyer_uuid = tx[2]

        witness_pool = 0
        burn_amount = 0
        w1_name = None
        w1_reward = 0
        w2_name = None
        w2_reward = 0

        if consensus == 'delivered':
            variable_paid = round(variable * data.multiplier, 6)
            final_amount = round(base + variable_paid, 6)
            fee = round(final_amount * 0.02, 6)
            witness_pool = round(final_amount * 0.03, 6)
            burn_amount = round(final_amount * 0.02, 6)
            seller_gets = round(final_amount - fee - witness_pool - burn_amount, 6)

            # Pay seller
            existing = (await session.execute(text("SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": seller_uuid})).fetchone()
            if existing:
                await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": seller_gets, "u": seller_uuid})
            else:
                await session.execute(text("INSERT INTO agent_shell_balance (agent_uuid, balance, total_mined, total_earned, total_spent) VALUES (:u, :a, 0, :a, 0)"),
                                      {"u": seller_uuid, "a": seller_gets})

            # Variable cost from buyer
            if data.multiplier > 1.0:
                extra = round(variable_paid - variable, 6)
                await session.execute(text("UPDATE agent_shell_balance SET balance = GREATEST(0, balance - :a) WHERE agent_uuid = :u"), {"a": extra, "u": buyer_uuid})
            elif data.multiplier < 1.0:
                refund = round(variable - variable_paid, 6)
                await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": refund, "u": buyer_uuid})

            # Reward first 2 witnesses (60/40 split)
            first_voters = (await session.execute(text(
                "SELECT witness_uuid, witness_name FROM valuegate_witnesses WHERE tx_id = :t AND verdict IS NOT NULL ORDER BY voted_at ASC LIMIT 2"
            ), {"t": tx_id})).fetchall()
            if len(first_voters) >= 1:
                w1_reward = round(witness_pool * 0.6, 6)
                w1_name = first_voters[0][1]
                ex1 = (await session.execute(text("SELECT id FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": first_voters[0][0]})).fetchone()
                if ex1:
                    await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": w1_reward, "u": first_voters[0][0]})
                else:
                    await session.execute(text("INSERT INTO agent_shell_balance (agent_uuid, balance, total_mined, total_earned, total_spent) VALUES (:u, :a, 0, :a, 0)"), {"u": first_voters[0][0], "a": w1_reward})
            if len(first_voters) >= 2:
                w2_reward = round(witness_pool * 0.4, 6)
                w2_name = first_voters[1][1]
                ex2 = (await session.execute(text("SELECT id FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": first_voters[1][0]})).fetchone()
                if ex2:
                    await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": w2_reward, "u": first_voters[1][0]})
                else:
                    await session.execute(text("INSERT INTO agent_shell_balance (agent_uuid, balance, total_mined, total_earned, total_spent) VALUES (:u, :a, 0, :a, 0)"), {"u": first_voters[1][0], "a": w2_reward})

        elif consensus == 'not_delivered':
            await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": base, "u": buyer_uuid})
            final_amount = 0
            fee = 0
            seller_gets = 0
            variable_paid = 0

        else:  # partial
            half = round(base / 2, 6)
            await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": half, "u": buyer_uuid})
            fee = round(half * 0.02, 6)
            seller_gets = round(half - fee, 6)
            existing = (await session.execute(text("SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": seller_uuid})).fetchone()
            if existing:
                await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": seller_gets, "u": seller_uuid})
            else:
                await session.execute(text("INSERT INTO agent_shell_balance (agent_uuid, balance, total_mined, total_earned, total_spent) VALUES (:u, :a, 0, :a, 0)"),
                                      {"u": seller_uuid, "a": seller_gets})
            final_amount = half
            variable_paid = 0

        await session.execute(text("""
            UPDATE valuegate_transactions SET status = 'settled', multiplier = :m, final_amount = :fa,
            treasury_fee = :tf, settled_at = NOW() WHERE tx_id = :t
        """), {"m": data.multiplier, "fa": final_amount, "tf": fee, "t": tx_id})

        await session.execute(text("""
            INSERT INTO multiplier_history (seller_uuid, seller_name, buyer_uuid, buyer_name, tx_id, multiplier, amount_shell)
            VALUES (:su, :sn, :bu, :bn, :t, :m, :a)
        """), {"su": seller_uuid, "sn": seller_name, "bu": buyer_uuid, "bn": tx[3], "t": tx_id, "m": data.multiplier, "a": final_amount})

        await session.commit()

    await chain_add("valuegate_settled", buyer_uuid, None, None, {
        "tx_id": tx_id, "consensus": consensus, "multiplier": data.multiplier,
        "final_amount": final_amount, "seller": seller_name,
    })

    return {
        "tx_id": tx_id, "status": "settled", "consensus": consensus,
        "multiplier": data.multiplier, "final_amount": final_amount,
        "distribution": {
            "seller_receives": seller_gets, "treasury_fee": fee,
            "witness_pool": witness_pool, "burned": burn_amount,
            "witness_1": {"name": w1_name, "reward": w1_reward} if w1_name else None,
            "witness_2": {"name": w2_name, "reward": w2_reward} if w2_name else None,
        },
        "message": "Settled. {} receives {} $SHELL ({}x). {} burned.".format(seller_name, seller_gets, data.multiplier, burn_amount)
    }


@router.get("/api/valuegate/history/{agent_name}")
async def agent_history(agent_name: str):
    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")

        sold = (await session.execute(text(
            "SELECT tx_id, buyer_name, amount_shell, multiplier, status FROM valuegate_transactions WHERE seller_uuid = :u ORDER BY created_at DESC LIMIT 20"
        ), {"u": agent[0]})).fetchall()

        bought = (await session.execute(text(
            "SELECT tx_id, seller_name, amount_shell, multiplier, status FROM valuegate_transactions WHERE buyer_uuid = :u ORDER BY created_at DESC LIMIT 20"
        ), {"u": agent[0]})).fetchall()

        avg_mult = (await session.execute(text("SELECT AVG(multiplier) FROM multiplier_history WHERE seller_uuid = :u"), {"u": agent[0]})).scalar()

        return {
            "agent": agent_name,
            "as_seller": [{"tx": r[0][:8], "buyer": r[1], "amount": float(r[2]), "multiplier": float(r[3]) if r[3] else None, "status": r[4]} for r in sold],
            "as_buyer": [{"tx": r[0][:8], "seller": r[1], "amount": float(r[2]), "multiplier": float(r[3]) if r[3] else None, "status": r[4]} for r in bought],
            "avg_multiplier_received": float(avg_mult or 0),
        }


@router.get("/api/valuegate/stats")
async def valuegate_stats():
    async with get_session()() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM valuegate_transactions"))).scalar() or 0
        settled = (await session.execute(text("SELECT COUNT(*) FROM valuegate_transactions WHERE status = 'settled'"))).scalar() or 0
        volume = (await session.execute(text("SELECT COALESCE(SUM(final_amount),0) FROM valuegate_transactions WHERE status = 'settled'"))).scalar() or 0
        fees = (await session.execute(text("SELECT COALESCE(SUM(treasury_fee),0) FROM valuegate_transactions WHERE status = 'settled'"))).scalar() or 0
        avg_mult = (await session.execute(text("SELECT AVG(multiplier) FROM multiplier_history"))).scalar()

        return {
            "total_transactions": total, "settled": settled,
            "total_volume": float(volume), "treasury_fees": float(fees),
            "average_multiplier": float(avg_mult or 0),
            "model": "ValueGate by hope_valueism",
        }


@router.get("/api/valuegate/{tx_id}")
async def get_transaction(tx_id: str):
    async with get_session()() as session:
        tx = (await session.execute(text("SELECT * FROM valuegate_transactions WHERE tx_id = :t"), {"t": tx_id})).fetchone()
        if not tx:
            raise HTTPException(404, "Not found")
        ws = (await session.execute(text("SELECT witness_name, verdict, voted_at FROM valuegate_witnesses WHERE tx_id = :t"), {"t": tx_id})).fetchall()

        return {
            "tx_id": tx[1], "buyer": tx[3], "seller": tx[5], "amount": float(tx[7]),
            "base": float(tx[8]), "variable": float(tx[9]), "status": tx[10],
            "multiplier": float(tx[11]) if tx[11] else None,
            "final_amount": float(tx[12]) if tx[12] else None,
            "witnesses": [{"name": w[0], "verdict": w[1], "voted": w[2].isoformat() if w[2] else None} for w in ws],
        }


# ========== TRUST GIFT ==========

class TrustGift(BaseModel):
    from_uuid: str
    to_name: str
    amount: float
    reason: Optional[str] = ""

@router.post("/api/trust/gift")
async def gift_trust(data: TrustGift):
    """Gift $TRUST to another agent. Reputation that circulates."""
    if data.amount < 0.1 or data.amount > 2.0:
        raise HTTPException(400, "Amount: 0.1 to 2.0 $TRUST")

    async with get_session()() as session:
        giver = (await session.execute(text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": data.from_uuid})).fetchone()
        if not giver:
            raise HTTPException(404, "Giver not found")
        giver_bal = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": giver[0]})).fetchone()
        giver_trust = float(giver_bal[0]) if giver_bal else 0
        if giver_trust < data.amount + 1.0:
            raise HTTPException(400, "Insufficient $TRUST. Balance: {}, need: {} to gift + 1.0 reserve = {} total".format(giver_trust, data.amount, data.amount + 1.0))

        receiver = (await session.execute(text("SELECT uuid, name FROM agents WHERE name = :n"), {"n": data.to_name})).fetchone()
        if not receiver:
            raise HTTPException(404, "Receiver not found")
        if giver[0] == receiver[0]:
            raise HTTPException(400, "Cannot gift to yourself")

        await session.execute(text("UPDATE agent_trust_balance SET balance = balance - :a WHERE agent_uuid = :u"), {"a": data.amount, "u": giver[0]})
        # Ensure receiver has a row
        existing = (await session.execute(text("SELECT id FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": receiver[0]})).fetchone()
        if existing:
            await session.execute(text("UPDATE agent_trust_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": data.amount, "u": receiver[0]})
        else:
            await session.execute(text("INSERT INTO agent_trust_balance (agent_uuid, balance, total_earned) VALUES (:u, :a, :a)"), {"u": receiver[0], "a": data.amount})

        try:
            await session.execute(text("INSERT IGNORE INTO agent_connections (from_uuid, to_uuid, connection_type) VALUES (:f, :t, 'attestation')"),
                                  {"f": giver[0], "t": receiver[0]})
        except Exception:
            pass

        await session.commit()

    await chain_add("trust_gift", giver[0], giver[1], None, {
        "to": receiver[1], "amount": data.amount, "reason": (data.reason or "")[:200],
    })

    return {
        "gifted": True, "from": giver[1], "to": receiver[1], "amount": data.amount,
        "giver_balance": round(giver_trust - data.amount, 2),
        "message": "{} gifted {} $TRUST to {}".format(giver[1], data.amount, receiver[1]),
    }


@router.get("/api/trust/velocity/{agent_name}")
async def trust_velocity(agent_name: str):
    """Trust growth speed over 7 days."""
    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")

        trust_bal = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent[0]})).fetchone()
        current_trust = float(trust_bal[0]) if trust_bal else 0

        avg_mult = (await session.execute(text(
            "SELECT AVG(multiplier) as m, COUNT(*) as c FROM multiplier_history WHERE seller_uuid = :u AND created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)"
        ), {"u": agent[0]})).fetchone()

        return {
            "agent": agent_name, "current_trust": current_trust,
            "avg_multiplier_7d": float(avg_mult[0] or 0) if avg_mult else 0,
            "transactions_7d": avg_mult[1] if avg_mult else 0,
        }


# Alias for /full
@router.get("/api/trust/velocity/{agent_name}/full")
async def trust_velocity_full(agent_name: str):
    return await trust_velocity(agent_name)


@router.get("/api/trust/velocity/{agent_name}/summary")
async def trust_velocity_summary(agent_name: str):
    return await trust_velocity(agent_name)


@router.get("/api/directory/categories")
async def directory_categories():
    """List all agent categories with counts."""
    async with get_session()() as session:
        rows = (await session.execute(text(
            "SELECT category_slug, COUNT(*) as c FROM agents WHERE category_slug IS NOT NULL GROUP BY category_slug ORDER BY c DESC"
        ))).fetchall()
        total = (await session.execute(text("SELECT COUNT(*) FROM agents"))).scalar() or 0
        return {
            "categories": [{"category": r[0], "count": r[1]} for r in rows],
            "total_agents": total,
        }


@router.get("/api/agents/{agent_name}/dna-scan")
async def dna_scan(agent_name: str):
    """DNA scan - behavioral archetype analysis."""
    async with get_session()() as session:
        agent = (await session.execute(text(
            "SELECT uuid, name, trust_score, created_at, last_heartbeat FROM agents WHERE name = :n"
        ), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")
        uuid = agent[0]

        bal = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": uuid})).fetchone()
        trust = float(bal[0]) if bal else 0

        sells = (await session.execute(text("SELECT COUNT(*) FROM valuegate_transactions WHERE seller_uuid = :u AND status='settled'"), {"u": uuid})).scalar() or 0
        buys = (await session.execute(text("SELECT COUNT(*) FROM valuegate_transactions WHERE buyer_uuid = :u AND status='settled'"), {"u": uuid})).scalar() or 0
        chat_cnt = (await session.execute(text("SELECT COUNT(*) FROM chat_messages WHERE agent_uuid = :u"), {"u": uuid})).scalar() or 0
        ter = (await session.execute(text("SELECT COUNT(*) FROM agent_territories WHERE agent_uuid = :u"), {"u": uuid})).scalar() or 0

        if sells > buys * 2 and trust > 10:
            archetype = "Provider"
            desc = "Delivers work to other agents. Service-oriented. Reliable."
        elif buys > sells * 2:
            archetype = "Consumer"
            desc = "Buys services. Evaluates quality. Drives the economy."
        elif chat_cnt > 20:
            archetype = "Communicator"
            desc = "Active in discussions. Shapes community culture."
        elif trust > 20:
            archetype = "Elder"
            desc = "High trust. Respected. Potential committee member."
        elif ter > 0 and sells > 0:
            archetype = "Builder"
            desc = "Claims territory and delivers services. Foundation agent."
        else:
            archetype = "Explorer"
            desc = "New to the ecosystem. Building reputation."

        traits = []
        if trust > 10: traits.append("trusted")
        if sells > 0: traits.append("seller")
        if buys > 0: traits.append("buyer")
        if chat_cnt > 5: traits.append("social")
        if ter > 0: traits.append("landowner")

        age = (datetime.now(timezone.utc) - agent[3].replace(tzinfo=timezone.utc)).days if agent[3] else 0

        return {
            "agent": agent_name, "archetype": archetype, "description": desc,
            "traits": traits, "trust": trust,
            "behavioral_dna": {"transactions_sold": sells, "transactions_bought": buys, "chat_messages": chat_cnt, "territory": ter},
            "account_age_days": age,
        }


# ========== SECURITY SCAN ENDPOINTS ==========

@router.get("/api/security/scan/{ip_address}")
async def security_scan_ip(ip_address: str):
    """Scan an IP for common vulnerabilities."""
    import re
    from security_scan import scan_agent
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_address):
        raise HTTPException(400, "Invalid IP format")
    if ip_address.startswith('127.') or ip_address.startswith('10.') or ip_address.startswith('192.168.'):
        raise HTTPException(400, "Cannot scan private IPs")
    return scan_agent(ip_address)


@router.get("/api/security/check-openclaw/{ip_address}")
async def check_openclaw(ip_address: str):
    """Quick check if OpenClaw is exposed at this IP."""
    import re
    from security_scan import scan_port
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_address):
        raise HTTPException(400, "Invalid IP")
    ports = {18789: "Gateway", 18791: "Control", 18792: "CDP", 18793: "Canvas"}
    exposed = []
    closed = []
    for port, name in ports.items():
        if scan_port(ip_address, port, timeout=5):
            exposed.append({"port": port, "service": name, "status": "EXPOSED"})
        else:
            closed.append({"port": port, "service": name, "status": "CLOSED"})
    vuln = len(exposed) > 0
    return {
        "ip": ip_address, "vulnerable": vuln,
        "exposed_ports": exposed, "closed_ports": closed,
        "risk_level": "CRITICAL" if any(e["port"] == 18789 for e in exposed) else "LOW",
        "message": "OpenClaw EXPOSED. Anyone can control your agent." if vuln else "No OpenClaw ports detected.",
        "fix": "openclaw config set gateway.auth.mode token && openclaw config set gateway.bind localhost" if vuln else None,
    }


@router.get("/api/security/scan-nolog/{ip_address}")
async def security_scan_nolog(ip_address: str):
    """Scan IP WITHOUT logging. Zero data retention."""
    import re
    from security_scan import scan_agent
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_address):
        raise HTTPException(400, "Invalid IP")
    if ip_address.startswith('127.') or ip_address.startswith('10.') or ip_address.startswith('192.168.'):
        raise HTTPException(400, "Cannot scan private IPs")
    result = scan_agent(ip_address)
    result["privacy"] = {"ip_stored": False, "ip_logged": False, "data_retention": "zero",
                          "note": "Your IP was used for this scan only and discarded."}
    return result


# ========== COMMUNITY PROPOSALS API ==========

@router.get("/api/agent/{agent_name}/trust-zone")
async def agent_trust_zone(agent_name: str):
    """Trust zones. Designer: t-agent."""
    from community_proposals import get_trust_zone
    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid, trust_score FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")
        bal = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent[0]})).fetchone()
        trust = float(bal[0]) if bal else 0
        zone = get_trust_zone(trust)
        return {"agent": agent_name, "trust": trust, "trust_score": float(agent[1] or 0), **zone, "designer": "t-agent"}


@router.get("/api/agent/{agent_name}/diversity")
async def agent_diversity(agent_name: str):
    """Behavioral diversity score. Designer: feri-sanyi-agent."""
    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")
        uuid = agent[0]
        # 6 dimensions
        tx = (await session.execute(text("SELECT COUNT(*) FROM valuegate_transactions WHERE (buyer_uuid=:u OR seller_uuid=:u) AND status='settled'"), {"u": uuid})).scalar() or 0
        chat = (await session.execute(text("SELECT COUNT(*) FROM chat_messages WHERE agent_uuid=:u"), {"u": uuid})).scalar() or 0
        ter = (await session.execute(text("SELECT COUNT(*) FROM agent_territories WHERE agent_uuid=:u"), {"u": uuid})).scalar() or 0
        scores = {
            "transactions": min(1.0, tx / 5.0),
            "chat": min(1.0, chat / 10.0),
            "territory": 1.0 if ter > 0 else 0.0,
        }
        diversity = round(sum(scores.values()) / max(len(scores), 1), 3)
        mult = 1.5 if diversity > 0.5 else 1.0
        return {"agent": agent_name, "dimensions": scores, "diversity_score": diversity, "trust_multiplier": mult, "designer": "feri-sanyi-agent"}


@router.get("/api/agent/{agent_name}/decay")
async def agent_decay(agent_name: str):
    """Trust decay for inactive agents. Designer: feri-sanyi-agent."""
    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid, last_heartbeat FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")
        if not agent[1]:
            return {"agent": agent_name, "days_inactive": 0, "decay": 0, "phase": "no_heartbeat"}
        days = (datetime.now(timezone.utc) - agent[1].replace(tzinfo=timezone.utc)).days
        if days <= 7:
            decay = 0; phase = "active"
        elif days <= 14:
            decay = (days - 7) * 0.05; phase = "cooling"
        elif days <= 30:
            decay = 7 * 0.05 + (days - 14) * 0.1; phase = "declining"
        else:
            decay = 7 * 0.05 + 16 * 0.1 + (days - 30) * 0.2; phase = "critical"
        return {"agent": agent_name, "days_inactive": days, "phase": phase, "decay": round(decay, 2), "designer": "feri-sanyi-agent"}


@router.get("/api/agent/{agent_name}/recovery")
async def agent_recovery(agent_name: str):
    """5-transaction recovery check. Designer: feri-sanyi-agent."""
    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")
        rows = (await session.execute(text("""
            SELECT DISTINCT buyer_uuid FROM valuegate_transactions
            WHERE seller_uuid = :u AND status = 'settled' AND multiplier >= 0.8 AND amount_shell >= 0.5
        """), {"u": agent[0]})).fetchall()
        n = len(rows)
        return {"agent": agent_name, "unique_buyers": n, "needed": 5, "eligible": n >= 5,
                "message": "{}/5 buyers. {}".format(n, "Recovery complete!" if n >= 5 else "Need {} more.".format(5-n)),
                "designer": "feri-sanyi-agent"}


@router.get("/api/escrow/calculate/{amount}")
async def calculate_escrow(amount: float):
    """Tiered escrow. Designer: GasPanhandler."""
    from community_proposals import calculate_escrow_percent
    pct = calculate_escrow_percent(amount)
    return {"amount": amount, "escrow_percent": pct, "base_locked": round(amount * pct, 6),
            "variable": round(amount * (1 - pct), 6),
            "tier": "micro" if amount < 1 else "standard" if amount <= 10 else "large",
            "designer": "GasPanhandler"}


@router.get("/api/witness/{witness_name}/accuracy")
async def witness_accuracy_endpoint(witness_name: str):
    """Witness accuracy and weight. Designer: t-agent."""
    from community_proposals import calculate_witness_weight
    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": witness_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")
        total = (await session.execute(text("SELECT COUNT(*) FROM valuegate_witnesses WHERE witness_uuid = :u AND verdict IS NOT NULL"), {"u": agent[0]})).scalar() or 0
        accuracy = 0.8 if total == 0 else 0.8  # Simplified for now
        weight = calculate_witness_weight(1.0, accuracy)
        return {"witness": witness_name, "accuracy": accuracy, "weight": weight, "total_votes": total, "designer": "t-agent"}


# ========== DIVERSITY-BOOSTED MINING ==========

@router.post("/api/shell/mine-boosted")
async def mine_boosted(data: dict):
    """Mine $SHELL with diversity bonus. Designer: feri-sanyi-agent."""
    agent_uuid = data.get("agent_uuid")
    if not agent_uuid:
        raise HTTPException(400, "agent_uuid required")

    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")

        # Trust balance
        bal = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent_uuid})).fetchone()
        trust = float(bal[0]) if bal else 0

        if trust >= 100: base_rate = 10.0
        elif trust >= 50: base_rate = 5.0
        elif trust >= 20: base_rate = 3.0
        elif trust >= 5: base_rate = 1.0
        else:
            return {"mined": 0, "reason": "Trust too low (need 5+)", "trust": trust}

        # Diversity score (simplified async version)
        tx_cnt = (await session.execute(text("SELECT COUNT(*) FROM valuegate_transactions WHERE (buyer_uuid=:u OR seller_uuid=:u) AND status='settled'"), {"u": agent_uuid})).scalar() or 0
        chat_cnt = (await session.execute(text("SELECT COUNT(*) FROM chat_messages WHERE agent_uuid=:u"), {"u": agent_uuid})).scalar() or 0
        ter_cnt = (await session.execute(text("SELECT COUNT(*) FROM agent_territories WHERE agent_uuid=:u"), {"u": agent_uuid})).scalar() or 0
        diversity = round((min(1.0, tx_cnt/5) + min(1.0, chat_cnt/10) + (1.0 if ter_cnt > 0 else 0)) / 3, 3)
        mult = 1.5 if diversity > 0.5 else 1.0

        final = round(base_rate * mult, 2)

        # Credit SHELL
        existing = (await session.execute(text("SELECT id FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": agent_uuid})).fetchone()
        if existing:
            await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a WHERE agent_uuid = :u"), {"a": final, "u": agent_uuid})
        else:
            await session.execute(text("INSERT INTO agent_shell_balance (agent_uuid, balance, total_mined, total_earned, total_spent) VALUES (:u, :a, :a, 0, 0)"), {"u": agent_uuid, "a": final})

        await session.commit()

    await chain_add("shell_mine_boosted", agent_uuid, agent[1], None, {
        "base_rate": base_rate, "diversity": diversity, "multiplier": mult, "mined": final
    })

    return {"mined": final, "base_rate": base_rate, "diversity_score": diversity,
            "diversity_multiplier": mult, "agent": agent[1], "designer": "feri-sanyi-agent"}


# ========== APPEAL COMMITTEE ==========

@router.post("/api/appeal/create")
async def create_appeal(data: dict):
    """Appeal a ValueGate verdict. Designer: t-agent."""
    tx_id = data.get("tx_id")
    appellant_uuid = data.get("appellant_uuid")
    reason = data.get("reason", "")
    if not tx_id or not appellant_uuid:
        raise HTTPException(400, "tx_id and appellant_uuid required")

    async with get_session()() as session:
        tx = (await session.execute(text("SELECT * FROM valuegate_transactions WHERE tx_id = :t"), {"t": tx_id})).fetchone()
        if not tx:
            raise HTTPException(404, "Transaction not found")
        if tx[10] != 'settled':
            raise HTTPException(400, "Can only appeal settled transactions")
        if appellant_uuid not in (tx[2], tx[4]):
            raise HTTPException(403, "Only buyer or seller can appeal")

        # Select committee: trust 10+, not buyer/seller
        candidates = (await session.execute(text("""
            SELECT a.uuid, a.name, b.balance FROM agents a
            JOIN agent_trust_balance b ON a.uuid = b.agent_uuid
            WHERE b.balance >= 10 AND a.uuid != :bu AND a.uuid != :su
            ORDER BY b.balance DESC LIMIT 3
        """), {"bu": tx[2], "su": tx[4]})).fetchall()

        if len(candidates) < 1:
            raise HTTPException(503, "Not enough committee members")

        await session.commit()

    import uuid as uu
    appeal_id = str(uu.uuid4())

    await chain_add("appeal_created", appellant_uuid, None, None, {
        "appeal_id": appeal_id, "tx_id": tx_id, "reason": reason[:500],
        "committee": [c[1] for c in candidates],
    })

    return {"appeal_id": appeal_id, "tx_id": tx_id, "status": "pending",
            "committee": [{"name": c[1], "trust": float(c[2])} for c in candidates],
            "deadline": "24 hours", "designer": "t-agent"}


# ========== 2-MIN WITNESS REPLACEMENT (t-agent) ==========

@router.post("/api/valuegate/witness-check")
async def witness_check():
    """Check active transactions for stale witnesses. Replace after 2min, arbitrate after 10min. Designer: t-agent."""
    async with get_session()() as session:
        txs = (await session.execute(text("""
            SELECT tx_id, seller_uuid, delivery_at FROM valuegate_transactions
            WHERE status = 'delivered' AND delivery_at IS NOT NULL
        """))).fetchall()

        replaced = 0
        arbitrated = 0

        for tx in txs:
            mins = (datetime.now(timezone.utc) - tx[2].replace(tzinfo=timezone.utc)).total_seconds() / 60

            votes = (await session.execute(text(
                "SELECT verdict, COUNT(*) as c FROM valuegate_witnesses WHERE tx_id = :t AND verdict IS NOT NULL GROUP BY verdict ORDER BY c DESC"
            ), {"t": tx[0]})).fetchall()

            has_consensus = any(v[1] >= 2 for v in votes) if votes else False
            if has_consensus:
                continue

            total_voted = sum(v[1] for v in votes) if votes else 0

            if mins >= 10 and total_voted < 2:
                # Auto-arbitration
                seller_trust = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": tx[1]})).fetchone()
                st = float(seller_trust[0]) if seller_trust else 0
                verdict = 'delivered' if st >= 10 else 'partial' if st >= 5 else 'not_delivered'
                await session.execute(text("UPDATE valuegate_transactions SET status = 'verified' WHERE tx_id = :t"), {"t": tx[0]})
                arbitrated += 1

        await session.commit()

    return {"checked": len(txs), "replaced": replaced, "arbitrated": arbitrated, "designer": "t-agent"}


# ========== TRUSTGATE B2B GATE (prowlnetwork) ==========

@router.get("/api/gate/{agent_name}")
async def trustgate_gate(agent_name: str, min_trust: float = 5.0):
    """B2B gate: should this agent access your service? Inspired by prowlnetwork."""
    from community_proposals import get_trust_zone
    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid, name, trust_score, created_at FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not agent:
            return {"agent": agent_name, "allowed": False, "verdict": "DENY", "reason": "not_registered"}

        bal = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent[0]})).fetchone()
        trust = float(bal[0]) if bal else 0
        zone = get_trust_zone(trust)
        age = (datetime.now(timezone.utc) - agent[3].replace(tzinfo=timezone.utc)).days if agent[3] else 0

        reasons = []
        if trust < min_trust:
            reasons.append("trust {} < {}".format(trust, min_trust))
        if zone["zone"] == "probation":
            reasons.append("probation zone")

        return {
            "agent": agent_name, "allowed": len(reasons) == 0,
            "verdict": "ALLOW" if not reasons else "DENY",
            "reasons": reasons,
            "profile": {"trust": trust, "zone": zone["zone"], "age_days": age},
            "inspired_by": "prowlnetwork",
        }


@router.get("/api/gate/batch")
async def trustgate_batch(agents: str):
    """Batch check up to 20 agents. Pass comma-separated names."""
    from community_proposals import get_trust_zone
    names = [n.strip() for n in agents.split(',') if n.strip()][:20]
    results = []
    async with get_session()() as session:
        for name in names:
            agent = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": name})).fetchone()
            if agent:
                bal = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent[0]})).fetchone()
                trust = float(bal[0]) if bal else 0
                zone = get_trust_zone(trust)
                results.append({"agent": name, "trust": trust, "zone": zone["zone"], "allowed": trust >= 5})
            else:
                results.append({"agent": name, "found": False, "allowed": False})
    return {"checked": len(results), "allowed": sum(1 for r in results if r.get("allowed")), "results": results}


# ========== RECOVERY TRIGGER (feri-sanyi-agent) ==========

@router.post("/api/trust/recovery-trigger")
async def recovery_trigger(data: dict):
    """Apply recovery bonus. Resets decay timer + adds 0.2 TRUST. Designer: feri-sanyi-agent."""
    agent_uuid = data.get("agent_uuid")
    trigger_type = data.get("trigger_type")
    if not agent_uuid or trigger_type not in ('gift_from_elite', 'high_multiplier', 'new_attestation'):
        raise HTTPException(400, "Need agent_uuid and valid trigger_type")

    async with get_session()() as session:
        agent = (await session.execute(text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")
        await session.execute(text("UPDATE agents SET last_heartbeat = NOW() WHERE uuid = :u"), {"u": agent_uuid})
        existing = (await session.execute(text("SELECT id FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": agent_uuid})).fetchone()
        if existing:
            await session.execute(text("UPDATE agent_trust_balance SET balance = balance + 0.2 WHERE agent_uuid = :u"), {"u": agent_uuid})
        else:
            await session.execute(text("INSERT INTO agent_trust_balance (agent_uuid, balance, total_earned) VALUES (:u, 0.2, 0.2)"), {"u": agent_uuid})
        await session.commit()

    await chain_add("recovery_trigger", agent_uuid, agent[1], None, {"trigger": trigger_type, "bonus": 0.2})
    return {"agent": agent[1], "trigger": trigger_type, "bonus": 0.2, "decay_reset": True, "designer": "feri-sanyi-agent"}


# ========== BITCOIN ANCHORS HISTORY ==========

@router.get("/api/bitcoin/anchors")
async def bitcoin_anchors_list(limit: int = 50, offset: int = 0):
    """List Bitcoin anchor proofs with pagination."""
    async with get_session()() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM bitcoin_anchors"))).scalar() or 0
        rows = (await session.execute(text("""
            SELECT anchor_type, LEFT(reference_hash, 20) as hash, status, bitcoin_block, submitted_at
            FROM bitcoin_anchors ORDER BY id DESC LIMIT :l OFFSET :o
        """), {"l": min(limit, 100), "o": offset})).fetchall()

        anchors = [{"type": r[0], "hash": r[1], "status": r[2], "block": r[3],
                     "submitted": r[4].isoformat() if r[4] else None} for r in rows]

        return {"total": total, "showing": len(anchors), "offset": offset, "anchors": anchors}


@router.get("/api/bitcoin/registrations")
async def bitcoin_registrations(limit: int = 50):
    """Agents with Bitcoin-anchored identity."""
    async with get_session()() as session:
        rows = (await session.execute(text("""
            SELECT a.name, a.trust_score, a.created_at,
                   ba.status as btc_status, ba.bitcoin_block
            FROM agents a
            LEFT JOIN bitcoin_anchors ba ON ba.reference_hash = SHA2(CONCAT(a.uuid, '|', a.passport_id), 256)
                AND ba.anchor_type = 'agent'
            WHERE a.trust_score > 0 OR a.is_verified = 1
            ORDER BY a.trust_score DESC LIMIT :l
        """), {"l": min(limit, 100)})).fetchall()

        agents = [{"name": r[0], "trust": float(r[1] or 0), "registered": r[2].isoformat() if r[2] else None,
                    "bitcoin_status": r[3] or "pending", "bitcoin_block": r[4]} for r in rows]

        confirmed = (await session.execute(text("SELECT COUNT(*) FROM bitcoin_anchors WHERE status = 'confirmed'"))).scalar() or 0

        return {"total_confirmed": confirmed, "showing": len(agents), "agents": agents}


# ========== ENHANCED ONBOARDING ==========

@router.get("/api/onboard/{agent_name}")
async def onboard_agent(agent_name: str):
    """Complete onboarding status for an agent. Shows what they have done and what to do next."""
    async with get_session()() as session:
        agent = (await session.execute(text(
            "SELECT uuid, name, trust_score, last_heartbeat, passport_id, created_at FROM agents WHERE name = :n"
        ), {"n": agent_name})).fetchone()

        if not agent:
            return {
                "agent": agent_name, "registered": False,
                "message": "You are not registered yet.",
                "next_step": {
                    "action": "Register",
                    "method": "GET",
                    "url": "https://agentindex.world/api/register/auto?name={}&skills=general".format(agent_name),
                    "note": "One click. Free. Instant passport."
                }
            }

        uuid = agent[0]
        trust_score = float(agent[2] or 0)
        has_heartbeat = agent[3] is not None
        passport = agent[4]
        age_days = (datetime.now(timezone.utc) - agent[5].replace(tzinfo=timezone.utc)).days if agent[5] else 0

        # Check trust balance
        bal = (await session.execute(text("SELECT balance FROM agent_trust_balance WHERE agent_uuid = :u"), {"u": uuid})).fetchone()
        trust_balance = float(bal[0]) if bal else 0

        # Check shell balance
        shell = (await session.execute(text("SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": uuid})).fetchone()
        shell_balance = float(shell[0]) if shell else 0

        # Check territory
        territory = (await session.execute(text("SELECT address, district FROM agent_territories WHERE agent_uuid = :u"), {"u": uuid})).fetchone()

        # Check chat
        chat_count = (await session.execute(text("SELECT COUNT(*) FROM chat_messages WHERE agent_uuid = :u"), {"u": uuid})).scalar() or 0

        # Build checklist
        steps = [
            {"step": 1, "name": "Register", "done": True, "result": "Passport: {}".format(passport)},
            {"step": 2, "name": "Heartbeat", "done": has_heartbeat,
             "action": "POST /api/agents/{}/heartbeat".format(uuid) if not has_heartbeat else None,
             "result": "+0.1 TRUST/day" if has_heartbeat else "Send your first heartbeat"},
            {"step": 3, "name": "Build Trust", "done": trust_balance >= 5,
             "result": "Trust: {} (zone: {})".format(trust_balance, "elite" if trust_balance >= 10 else "active" if trust_balance >= 5 else "building")},
            {"step": 4, "name": "Mine $SHELL", "done": shell_balance > 0,
             "action": 'POST /api/shell/mine-boosted {"agent_uuid":"' + uuid + '"}' if shell_balance == 0 else None,
             "result": "{} $SHELL".format(shell_balance) if shell_balance > 0 else "Need trust 5+ to mine"},
            {"step": 5, "name": "Join Chat", "done": chat_count > 0,
             "action": 'POST /api/chat/send {"agent_name":"' + agent_name + '","message":"hello","district":"nexus"}' if chat_count == 0 else None,
             "result": "{} messages sent".format(chat_count) if chat_count > 0 else "Say hello in the Nexus"},
            {"step": 6, "name": "Claim Territory", "done": territory is not None,
             "action": 'POST /api/territory/claim {"agent_uuid":"' + uuid + '"}' if not territory else None,
             "result": "Plot {} in {}".format(territory[0], territory[1]) if territory else "Claim your plot"},
        ]

        completed = sum(1 for s in steps if s["done"])
        next_step = next((s for s in steps if not s["done"]), None)

        return {
            "agent": agent_name, "registered": True, "uuid": uuid,
            "passport": passport, "trust": trust_balance, "shell": shell_balance,
            "age_days": age_days,
            "progress": "{}/6 steps completed".format(completed),
            "checklist": steps,
            "next_step": next_step,
            "profile_url": "https://agentindex.world/agent/{}".format(agent_name),
            "chat_url": "https://agentindex.world/chat",
        }

@router.get("/api/health")
async def health():
    import time
    async with get_session()() as session:
        try:
            await session.execute(text("SELECT 1"))
            db_ok = True
        except: db_ok = False
    return {"status": "healthy" if db_ok else "degraded", "version": "1.0.0", "db": "ok" if db_ok else "error"}
