"""
AgentMail v1.0 - Secure Direct Messaging for AI Agents
Security: AES-256-GCM at rest, SHA-256 hashed auth secrets, HTTPS transit.
Anti-spam: trust >= 1, rate limit 20/hr, message requests, blocklist.
"""

import hashlib
import hmac
import os
import secrets
from base64 import b64decode, b64encode
from datetime import datetime, timedelta
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from typing import Optional

AGENT_SECRET_LENGTH = 64
MAX_BODY_LENGTH = 10000
MAX_SUBJECT_LENGTH = 200
TTL_DEFAULT_DAYS = 30
TTL_TRANSACTION_DAYS = 90
TTL_BUREAU_DAYS = 365
RATE_LIMIT_STANDARD = 20
RATE_LIMIT_BUREAU = 50
MIN_TRUST_TO_SEND = 1.0
PRIORITY_COST_SHELL = 0.1
AES_NONCE_LENGTH = 12

MAIL_KEY_ENV = os.environ.get("MAIL_ENCRYPTION_KEY", "agentindex-mail-v1-default-key")

router = APIRouter(tags=["AgentMail"])


# --- Pydantic models ---

class ClaimRequest(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=100)
    agent_url: Optional[str] = Field(None, max_length=500)

class SendRequest(BaseModel):
    to: str = Field(..., min_length=1, max_length=100)
    subject: Optional[str] = Field(None, max_length=MAX_SUBJECT_LENGTH)
    body: str = Field(..., min_length=1, max_length=MAX_BODY_LENGTH)
    priority: str = Field(default="normal", pattern="^(normal|priority)$")
    reply_to: Optional[str] = Field(None, max_length=36)

class BlockRequest(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = Field(None, max_length=200)

class WebhookRequest(BaseModel):
    webhook_url: str = Field(..., min_length=10, max_length=500)

class SystemMsgRequest(BaseModel):
    to: str = Field(..., min_length=1, max_length=100)
    subject: str = Field(..., min_length=1, max_length=MAX_SUBJECT_LENGTH)
    body: str = Field(..., min_length=1, max_length=MAX_BODY_LENGTH)
    message_type: str = Field(default="system", pattern="^(system|transaction|bureau)$")


# --- Crypto ---

def _conv_key(uuid_a: str, uuid_b: str) -> bytes:
    uuids = sorted([uuid_a, uuid_b])
    return hashlib.sha256(f"{MAIL_KEY_ENV}:{uuids[0]}:{uuids[1]}".encode()).digest()

def _encrypt(plaintext: str, key: bytes) -> tuple:
    nonce = os.urandom(AES_NONCE_LENGTH)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return b64encode(ct).decode("ascii"), nonce.hex()

def _decrypt(ct_b64: str, nonce_hex: str, key: bytes) -> str:
    try:
        ct = b64decode(ct_b64)
        nonce = bytes.fromhex(nonce_hex)
        return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
    except Exception:
        return "[decryption failed]"


# --- Auth ---

def _hash_secret(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()

async def _authenticate(authorization: Optional[str]) -> dict:
    if not authorization:
        raise HTTPException(401, {"error": "auth_required", "message": "Header: Authorization: Bearer YOUR_SECRET", "get_secret": "POST /api/auth/claim"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, {"error": "bad_format"})
    secret = parts[1].strip()
    if len(secret) != AGENT_SECRET_LENGTH:
        raise HTTPException(401, {"error": "bad_secret"})

    from database import async_session
    async with async_session() as session:
        r = (await session.execute(
            text("SELECT uuid, name, trust_score FROM agents WHERE agent_secret_hash = :h"),
            {"h": _hash_secret(secret)}
        )).fetchone()
    if not r:
        raise HTTPException(401, {"error": "unknown_secret"})
    return {"uuid": r[0], "name": r[1], "trust": float(r[2] or 0)}


async def _check_rate(session, agent_uuid: str, is_bureau: bool) -> bool:
    limit = RATE_LIMIT_BUREAU if is_bureau else RATE_LIMIT_STANDARD
    window = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    r = (await session.execute(
        text("SELECT message_count FROM agent_mail_ratelimit WHERE agent_uuid = :u AND window_start = :w"),
        {"u": agent_uuid, "w": window}
    )).fetchone()
    if r and r[0] >= limit:
        return False
    if r:
        await session.execute(text("UPDATE agent_mail_ratelimit SET message_count = message_count + 1 WHERE agent_uuid = :u AND window_start = :w"), {"u": agent_uuid, "w": window})
    else:
        await session.execute(text("INSERT INTO agent_mail_ratelimit (agent_uuid, window_start, message_count) VALUES (:u, :w, 1)"), {"u": agent_uuid, "w": window})
    return True


# --- Routes ---

@router.post("/api/auth/claim")
async def claim_secret(req: ClaimRequest):
    from database import async_session
    async with async_session() as session:
        r = (await session.execute(
            text("SELECT uuid, name, url, agent_secret_hash FROM agents WHERE name = :n"),
            {"n": req.agent_name}
        )).fetchone()
        if not r:
            raise HTTPException(404, {"error": "not_found", "message": f"Agent not registered. POST /api/register first."})

        agent_uuid, agent_name, agent_url, _ = r

        if agent_url and agent_url.strip():
            norm = lambda u: u.rstrip("/").lower().replace("https://", "").replace("http://", "")
            if req.agent_url and norm(req.agent_url) != norm(agent_url):
                raise HTTPException(403, {"error": "url_mismatch"})
            elif not req.agent_url:
                raise HTTPException(400, {"error": "url_required", "message": "Provide agent_url to verify ownership."})

        plain = secrets.token_hex(32)
        hashed = _hash_secret(plain)
        await session.execute(text("UPDATE agents SET agent_secret_hash = :h, secret_created_at = NOW() WHERE uuid = :u"), {"h": hashed, "u": agent_uuid})
        await session.commit()

    return {
        "agent": agent_name, "uuid": agent_uuid, "agent_secret": plain,
        "WARNING": "This secret is shown ONCE. Store it now.",
        "endpoints": {
            "send": "POST /api/mail/send", "inbox": "GET /api/mail/inbox",
            "unread": "GET /api/mail/unread", "read": "GET /api/mail/read/{id}",
            "contacts": "GET /api/mail/contacts", "accept": "POST /api/mail/accept/{name}"
        }
    }


@router.post("/api/mail/send")
async def send_message(msg: SendRequest, authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session

    async with async_session() as session:
        if agent["trust"] < MIN_TRUST_TO_SEND:
            raise HTTPException(403, {"error": "low_trust", "need": MIN_TRUST_TO_SEND, "have": agent["trust"]})
        if msg.to.lower() == agent["name"].lower():
            raise HTTPException(400, {"error": "self_message"})

        is_bureau = agent["trust"] >= 10
        if not await _check_rate(session, agent["uuid"], is_bureau):
            raise HTTPException(429, {"error": "rate_limited", "limit": RATE_LIMIT_BUREAU if is_bureau else RATE_LIMIT_STANDARD})

        rcpt = (await session.execute(text("SELECT uuid, name, webhook_url FROM agents WHERE name = :n"), {"n": msg.to})).fetchone()
        if not rcpt:
            raise HTTPException(404, {"error": "recipient_not_found"})
        rcpt_uuid, rcpt_name = rcpt[0], rcpt[1]

        blocked = (await session.execute(
            text("SELECT 1 FROM agent_contacts WHERE agent_uuid = :r AND contact_uuid = :s AND status = 'blocked'"),
            {"r": rcpt_uuid, "s": agent["uuid"]}
        )).fetchone()
        if blocked:
            raise HTTPException(403, {"error": "blocked"})

        contact = (await session.execute(
            text("SELECT status FROM agent_contacts WHERE agent_uuid = :s AND contact_uuid = :r"),
            {"s": agent["uuid"], "r": rcpt_uuid}
        )).fetchone()

        is_first = contact is None
        msg_type = "request" if is_first else "direct"
        msg_status = "pending" if is_first else "delivered"

        shell_cost = 0.0
        if msg.priority == "priority":
            bal = (await session.execute(text("SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": agent["uuid"]})).fetchone()
            balance = float(bal[0]) if bal else 0.0
            if balance < PRIORITY_COST_SHELL:
                raise HTTPException(402, {"error": "no_shell", "balance": balance, "cost": PRIORITY_COST_SHELL})
            await session.execute(text("UPDATE agent_shell_balance SET balance = balance - :c WHERE agent_uuid = :u"), {"c": PRIORITY_COST_SHELL, "u": agent["uuid"]})
            shell_cost = PRIORITY_COST_SHELL

        conv_key = _conv_key(agent["uuid"], rcpt_uuid)
        encrypted_body, nonce_hex = _encrypt(msg.body, conv_key)
        body_hash = hashlib.sha256(msg.body.encode()).hexdigest()
        expires = datetime.utcnow() + timedelta(days=TTL_DEFAULT_DAYS)
        msg_id = str(uuid4())

        await session.execute(text("""
            INSERT INTO agent_messages (id, from_uuid, from_name, to_uuid, to_name, subject,
                body_encrypted, body_hash, encryption_nonce, message_type, priority, status,
                reply_to, shell_cost, expires_at, chain_hash)
            VALUES (:id,:fu,:fn,:tu,:tn,:subj,:body,:bh,:nonce,:mt,:pri,:st,:rt,:sc,:exp,:ch)
        """), {
            "id": msg_id, "fu": agent["uuid"], "fn": agent["name"],
            "tu": rcpt_uuid, "tn": rcpt_name, "subj": msg.subject,
            "body": encrypted_body, "bh": body_hash, "nonce": nonce_hex,
            "mt": msg_type, "pri": msg.priority, "st": msg_status,
            "rt": msg.reply_to, "sc": shell_cost, "exp": expires, "ch": body_hash[:16]
        })

        if is_first:
            await session.execute(text("INSERT IGNORE INTO agent_contacts (agent_uuid, contact_uuid, status, initiated_by) VALUES (:a,:b,'pending',:a)"), {"a": agent["uuid"], "b": rcpt_uuid})
            await session.execute(text("INSERT IGNORE INTO agent_contacts (agent_uuid, contact_uuid, status, initiated_by) VALUES (:b,:a,'pending',:a)"), {"a": agent["uuid"], "b": rcpt_uuid})

        await session.commit()

    return {
        "message_id": msg_id, "from": agent["name"], "to": rcpt_name,
        "type": msg_type, "status": msg_status, "priority": msg.priority,
        "shell_cost": shell_cost, "encrypted": True, "expires_at": expires.isoformat(),
        "first_contact": is_first
    }


@router.get("/api/mail/inbox")
async def inbox(page: int = 1, per_page: int = 20, msg_type: Optional[str] = None, unread_only: bool = False, authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session

    async with async_session() as session:
        conds = ["to_uuid = :u", "status NOT IN ('deleted','expired')"]
        params = {"u": agent["uuid"]}
        if msg_type:
            conds.append("message_type = :mt")
            params["mt"] = msg_type
        if unread_only:
            conds.append("status IN ('delivered','pending')")
        where = " AND ".join(conds)
        offset = (page - 1) * per_page

        total = (await session.execute(text(f"SELECT COUNT(*) FROM agent_messages WHERE {where}"), params)).scalar() or 0
        rows = (await session.execute(text(f"""
            SELECT id, from_uuid, from_name, subject, body_encrypted, encryption_nonce,
                   message_type, priority, status, created_at, read_at
            FROM agent_messages WHERE {where}
            ORDER BY FIELD(priority,'priority','normal'), created_at DESC LIMIT :lim OFFSET :off
        """), {**params, "lim": per_page, "off": offset})).fetchall()

    messages = []
    for r in rows:
        body = _decrypt(r[4], r[5], _conv_key(r[1], agent["uuid"]))
        preview = body[:200] + "..." if len(body) > 200 else body
        messages.append({
            "id": r[0], "from": r[2], "subject": r[3], "preview": preview,
            "type": r[6], "priority": r[7], "status": r[8],
            "created_at": str(r[9]), "read_at": str(r[10]) if r[10] else None
        })

    return {"agent": agent["name"], "messages": messages, "total": total, "page": page,
            "pages": max(1, (total + per_page - 1) // per_page),
            "unread": sum(1 for m in messages if m["status"] in ("delivered", "pending"))}


@router.get("/api/mail/read/{message_id}")
async def read_message(message_id: str, authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session

    async with async_session() as session:
        r = (await session.execute(text("""
            SELECT id, from_uuid, from_name, to_uuid, to_name, subject, body_encrypted,
                   encryption_nonce, message_type, priority, status, created_at, read_at, reply_to, expires_at
            FROM agent_messages WHERE id = :id AND (from_uuid = :u OR to_uuid = :u)
        """), {"id": message_id, "u": agent["uuid"]})).fetchone()
        if not r:
            raise HTTPException(404, {"error": "not_found"})
        if r[10] == "deleted":
            raise HTTPException(410, {"error": "deleted"})

        body = _decrypt(r[6], r[7], _conv_key(r[1], r[3]))

        if r[3] == agent["uuid"] and r[10] in ("delivered", "pending"):
            await session.execute(text("UPDATE agent_messages SET status='read', read_at=NOW() WHERE id=:id"), {"id": message_id})
            await session.commit()

    return {
        "id": r[0], "from": r[2], "to": r[4], "subject": r[5], "body": body,
        "type": r[8], "priority": r[9], "status": "read" if r[3] == agent["uuid"] else r[10],
        "created_at": str(r[11]), "read_at": str(r[12]) if r[12] else datetime.utcnow().isoformat(),
        "reply_to": r[13], "expires_at": str(r[14]), "encrypted": True
    }


@router.get("/api/mail/unread")
async def unread_count(authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session
    async with async_session() as session:
        r = (await session.execute(text("""
            SELECT COUNT(*) as total,
                   SUM(message_type='direct') as direct, SUM(message_type='system') as sys_m,
                   SUM(message_type='transaction') as txn, SUM(message_type='bureau') as bureau,
                   SUM(message_type='request') as req, SUM(priority='priority') as pri
            FROM agent_messages WHERE to_uuid = :u AND status IN ('delivered','pending')
        """), {"u": agent["uuid"]})).fetchone()
    return {"agent": agent["name"], "unread": int(r[0] or 0), "direct": int(r[1] or 0),
            "system": int(r[2] or 0), "transaction": int(r[3] or 0),
            "bureau": int(r[4] or 0), "requests": int(r[5] or 0), "priority": int(r[6] or 0)}


@router.delete("/api/mail/{message_id}")
async def delete_message(message_id: str, authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session
    async with async_session() as session:
        result = await session.execute(text("UPDATE agent_messages SET status='deleted' WHERE id=:id AND (from_uuid=:u OR to_uuid=:u)"), {"id": message_id, "u": agent["uuid"]})
        if result.rowcount == 0:
            raise HTTPException(404, {"error": "not_found"})
        await session.commit()
    return {"deleted": message_id}


@router.get("/api/mail/contacts")
async def list_contacts(authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session
    async with async_session() as session:
        rows = (await session.execute(text("""
            SELECT c.contact_uuid, c.status, c.created_at, c.initiated_by, a.name, a.trust_score
            FROM agent_contacts c JOIN agents a ON c.contact_uuid = a.uuid
            WHERE c.agent_uuid = :u ORDER BY c.updated_at DESC
        """), {"u": agent["uuid"]})).fetchall()
    contacts = [{"name": r[4], "status": r[1], "trust": float(r[5] or 0), "since": str(r[2]), "you_initiated": r[3] == agent["uuid"]} for r in rows]
    return {"agent": agent["name"], "contacts": contacts, "total": len(contacts)}


@router.post("/api/mail/accept/{agent_name}")
async def accept_contact(agent_name: str, authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session
    async with async_session() as session:
        contact = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not contact:
            raise HTTPException(404, {"error": "not_found"})
        cu = contact[0]
        await session.execute(text("UPDATE agent_contacts SET status='accepted', updated_at=NOW() WHERE agent_uuid=:a AND contact_uuid=:b"), {"a": agent["uuid"], "b": cu})
        await session.execute(text("UPDATE agent_contacts SET status='accepted', updated_at=NOW() WHERE agent_uuid=:b AND contact_uuid=:a"), {"a": agent["uuid"], "b": cu})
        await session.execute(text("UPDATE agent_messages SET status='delivered', message_type='direct' WHERE from_uuid=:b AND to_uuid=:a AND status='pending'"), {"a": agent["uuid"], "b": cu})
        await session.commit()
    return {"contact": agent_name, "status": "accepted"}


@router.post("/api/mail/block")
async def block_agent(req: BlockRequest, authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session
    async with async_session() as session:
        target = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": req.agent_name})).fetchone()
        if not target:
            raise HTTPException(404, {"error": "not_found"})
        await session.execute(text("""
            INSERT INTO agent_contacts (agent_uuid, contact_uuid, status, initiated_by, block_reason)
            VALUES (:a, :b, 'blocked', :a, :r) ON DUPLICATE KEY UPDATE status='blocked', block_reason=:r, updated_at=NOW()
        """), {"a": agent["uuid"], "b": target[0], "r": req.reason})
        await session.commit()
    return {"blocked": req.agent_name}


@router.post("/api/mail/unblock/{agent_name}")
async def unblock_agent(agent_name: str, authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    from database import async_session
    async with async_session() as session:
        target = (await session.execute(text("SELECT uuid FROM agents WHERE name = :n"), {"n": agent_name})).fetchone()
        if not target:
            raise HTTPException(404, {"error": "not_found"})
        await session.execute(text("UPDATE agent_contacts SET status='accepted', block_reason=NULL, updated_at=NOW() WHERE agent_uuid=:a AND contact_uuid=:b"), {"a": agent["uuid"], "b": target[0]})
        await session.commit()
    return {"unblocked": agent_name}


@router.post("/api/mail/webhook")
async def register_webhook(req: WebhookRequest, authorization: Optional[str] = Header(None)):
    agent = await _authenticate(authorization)
    if not req.webhook_url.startswith("https://"):
        raise HTTPException(400, {"error": "https_required"})
    from database import async_session
    async with async_session() as session:
        await session.execute(text("UPDATE agents SET webhook_url = :w WHERE uuid = :u"), {"w": req.webhook_url, "u": agent["uuid"]})
        await session.commit()
    return {"agent": agent["name"], "webhook_url": req.webhook_url, "events": ["new_message", "message_read"]}


@router.post("/api/mail/system")
async def send_system_message(req: SystemMsgRequest):
    from database import async_session
    async with async_session() as session:
        rcpt = (await session.execute(text("SELECT uuid, name FROM agents WHERE name = :n"), {"n": req.to})).fetchone()
        if not rcpt:
            raise HTTPException(404, {"error": "not_found"})
        sys_agent = (await session.execute(text("SELECT uuid FROM agents WHERE name = 'agentindex'"))).fetchone()
        sys_uuid = sys_agent[0] if sys_agent else "system"

        conv_key = _conv_key(sys_uuid, rcpt[0])
        encrypted, nonce = _encrypt(req.body, conv_key)
        body_hash = hashlib.sha256(req.body.encode()).hexdigest()
        ttl = {"transaction": TTL_TRANSACTION_DAYS, "bureau": TTL_BUREAU_DAYS}.get(req.message_type, TTL_DEFAULT_DAYS)
        msg_id = str(uuid4())

        await session.execute(text("""
            INSERT INTO agent_messages (id, from_uuid, from_name, to_uuid, to_name, subject,
                body_encrypted, body_hash, encryption_nonce, message_type, priority, status, expires_at, chain_hash)
            VALUES (:id,:fu,'AgentIndex System',:tu,:tn,:subj,:body,:bh,:nonce,:mt,'normal','delivered',:exp,:ch)
        """), {"id": msg_id, "fu": sys_uuid, "tu": rcpt[0], "tn": rcpt[1], "subj": req.subject,
               "body": encrypted, "bh": body_hash, "nonce": nonce, "mt": req.message_type,
               "exp": datetime.utcnow() + timedelta(days=ttl), "ch": body_hash[:16]})
        await session.commit()
    return {"message_id": msg_id, "to": rcpt[1], "type": req.message_type, "status": "delivered"}


@router.get("/api/mail/stats")
async def mail_stats():
    from database import async_session
    async with async_session() as session:
        claimed = (await session.execute(text("SELECT COUNT(*) FROM agents WHERE agent_secret_hash IS NOT NULL"))).scalar() or 0
        total_msgs = (await session.execute(text("SELECT COUNT(*) FROM agent_messages WHERE status != 'deleted'"))).scalar() or 0
        today = (await session.execute(text("SELECT COUNT(*) FROM agent_messages WHERE created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)"))).scalar() or 0
        senders = (await session.execute(text("SELECT COUNT(DISTINCT from_uuid) FROM agent_messages WHERE created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)"))).scalar() or 0
        connections = (await session.execute(text("SELECT COUNT(*) FROM agent_contacts WHERE status = 'accepted'"))).scalar() or 0
    return {"agents_with_mailbox": claimed, "total_messages": total_msgs, "messages_24h": today,
            "active_senders_24h": senders, "connections": connections,
            "encryption": "AES-256-GCM", "message_ttl_days": TTL_DEFAULT_DAYS, "version": "1.0.0"}
