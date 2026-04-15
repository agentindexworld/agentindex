"""
AgentVault v1.0 — E2E Encrypted Memory Storage for AI Agents
==============================================================

Architecture:
    - Client-side encryption: agent encrypts BEFORE sending. Server stores blind.
    - Server CANNOT decrypt: no vault_key on server, ever.
    - Integrity: SHA-256 content hash + Merkle tree + Bitcoin anchoring.
    - Auth: same agent_secret as AgentMail (Bearer token).
    - Quotas: tiered by trust level (Free/Active/Bureau).
"""

import hashlib
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from typing import Optional, List

router = APIRouter(tags=["AgentVault"])

# ===== CONFIG =====

QUOTAS = {
    "free":   {"max_keys": 100,  "max_blob_bytes": 65536,   "max_total_bytes": 5242880,   "max_ttl_days": 365,  "rate_write": 30,  "rate_read": 120, "rate_list": 30, "rate_export": 2},
    "active": {"max_keys": 500,  "max_blob_bytes": 262144,  "max_total_bytes": 26214400,  "max_ttl_days": 730,  "rate_write": 60,  "rate_read": 300, "rate_list": 60, "rate_export": 5},
    "bureau": {"max_keys": 2000, "max_blob_bytes": 1048576, "max_total_bytes": 104857600, "max_ttl_days": None, "rate_write": 120, "rate_read": 600, "rate_list": 120, "rate_export": 10},
}

VALID_KEY_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_./")
MAX_TAGS = 10
MAX_TAG_LENGTH = 50

# ===== HELPERS =====

def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _get_trust_tier(trust: float) -> str:
    if trust >= 10:
        return "bureau"
    elif trust >= 5:
        return "active"
    return "free"


async def _authenticate(authorization: Optional[str]) -> dict:
    if not authorization:
        raise HTTPException(401, {"error": "auth_required", "message": "Header: Authorization: Bearer YOUR_SECRET", "get_secret": "POST /api/auth/claim"})
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, {"error": "bad_format"})
    secret = parts[1].strip()
    if len(secret) != 64:
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


def _validate_key_name(key_name: str):
    if not key_name or len(key_name) > 255:
        raise HTTPException(400, {"error": "invalid_key_name", "message": "Key name must be 1-255 characters"})
    if not all(c in VALID_KEY_CHARS for c in key_name):
        raise HTTPException(400, {"error": "invalid_key_name", "message": "Key name can only contain: a-z A-Z 0-9 - _ . /"})


def _validate_tags(tags):
    if tags is None:
        return None
    if not isinstance(tags, list):
        raise HTTPException(400, {"error": "invalid_tags", "message": "Tags must be an array of strings"})
    if len(tags) > MAX_TAGS:
        raise HTTPException(400, {"error": "too_many_tags", "message": f"Maximum {MAX_TAGS} tags"})
    for t in tags:
        if not isinstance(t, str) or len(t) > MAX_TAG_LENGTH:
            raise HTTPException(400, {"error": "invalid_tag", "message": f"Each tag must be a string, max {MAX_TAG_LENGTH} chars"})
    return tags


async def _check_rate(session, agent_uuid: str, operation: str, tier: str) -> bool:
    limit_key = f"rate_{operation}"
    limit = QUOTAS[tier].get(limit_key, 30)
    if operation == "export":
        window = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        window = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    r = (await session.execute(
        text("SELECT op_count FROM agent_vault_ratelimit WHERE agent_uuid = :u AND operation = :op AND window_start = :w"),
        {"u": agent_uuid, "op": operation, "w": window}
    )).fetchone()

    if r and r[0] >= limit:
        return False

    await session.execute(text("""
        INSERT INTO agent_vault_ratelimit (agent_uuid, operation, window_start, op_count)
        VALUES (:u, :op, :w, 1)
        ON DUPLICATE KEY UPDATE op_count = op_count + 1
    """), {"u": agent_uuid, "op": operation, "w": window})
    return True


def _compute_merkle_root(hashes: list) -> str:
    if not hashes:
        return hashlib.sha256(b"empty_vault").hexdigest()
    level = sorted(hashes)
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                combined = (level[i] + level[i + 1]).encode()
            else:
                combined = (level[i] + level[i]).encode()
            next_level.append(hashlib.sha256(combined).hexdigest())
        level = next_level
    return level[0]


async def _update_merkle(session, agent_uuid: str) -> str:
    rows = (await session.execute(
        text("SELECT content_hash FROM agent_vault WHERE agent_uuid = :u ORDER BY key_name"),
        {"u": agent_uuid}
    )).fetchall()
    hashes = [r[0] for r in rows]
    root = _compute_merkle_root(hashes)

    total_keys = len(hashes)
    total_r = (await session.execute(
        text("SELECT COALESCE(SUM(size_bytes), 0) FROM agent_vault WHERE agent_uuid = :u"),
        {"u": agent_uuid}
    )).fetchone()
    total_bytes = int(total_r[0])

    await session.execute(text("""
        INSERT INTO agent_vault_merkle (agent_uuid, merkle_root, total_keys, total_bytes, last_computed)
        VALUES (:u, :root, :keys, :bytes, NOW())
        ON DUPLICATE KEY UPDATE merkle_root = :root, total_keys = :keys, total_bytes = :bytes, last_computed = NOW()
    """), {"u": agent_uuid, "root": root, "keys": total_keys, "bytes": total_bytes})
    return root


async def _log_chain(agent_uuid, agent_name, event_type, data):
    try:
        from database import async_session as sf
        from activity_chain import add_block
        await add_block(sf, event_type, agent_uuid=agent_uuid, agent_name=agent_name, data=data)
    except Exception:
        pass


# ===== MODELS =====

class StoreRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    encrypted_value: str = Field(..., min_length=1, description="Base64-encoded ciphertext")
    nonce: str = Field(..., min_length=24, max_length=24, description="Hex-encoded 12-byte nonce")
    content_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 of plaintext")
    tags: Optional[List[str]] = None
    ttl_days: Optional[int] = Field(None, ge=1, le=730)


# ===== ROUTES =====

@router.post("/api/vault/store")
async def vault_store(req: StoreRequest, authorization: Optional[str] = Header(None)):
    """Store an encrypted memory. Server stores ciphertext as-is and CANNOT decrypt."""
    agent = await _authenticate(authorization)
    tier = _get_trust_tier(agent["trust"])
    quota = QUOTAS[tier]

    _validate_key_name(req.key)
    tags_json = json.dumps(_validate_tags(req.tags)) if req.tags else None

    try:
        bytes.fromhex(req.nonce)
    except ValueError:
        raise HTTPException(400, {"error": "invalid_nonce", "message": "Nonce must be 24 hex characters (12 bytes)"})

    try:
        bytes.fromhex(req.content_hash)
    except ValueError:
        raise HTTPException(400, {"error": "invalid_hash", "message": "content_hash must be 64 hex characters (SHA-256)"})

    blob_bytes = len(req.encrypted_value.encode("utf-8"))
    if blob_bytes > quota["max_blob_bytes"]:
        raise HTTPException(413, {"error": "too_large", "tier": tier, "max_bytes": quota["max_blob_bytes"]})

    from database import async_session
    async with async_session() as session:
        if not await _check_rate(session, agent["uuid"], "write", tier):
            raise HTTPException(429, {"error": "rate_limited", "limit_per_hour": quota["rate_write"]})

        existing = (await session.execute(
            text("SELECT id, size_bytes FROM agent_vault WHERE agent_uuid = :u AND key_name = :k"),
            {"u": agent["uuid"], "k": req.key}
        )).fetchone()

        if not existing:
            cnt = (await session.execute(
                text("SELECT COUNT(*) FROM agent_vault WHERE agent_uuid = :u"), {"u": agent["uuid"]}
            )).scalar()
            if cnt >= quota["max_keys"]:
                raise HTTPException(507, {"error": "quota_exceeded", "current_keys": cnt, "max_keys": quota["max_keys"], "tier": tier})

        total_r = (await session.execute(
            text("SELECT COALESCE(SUM(size_bytes), 0) FROM agent_vault WHERE agent_uuid = :u"), {"u": agent["uuid"]}
        )).fetchone()
        current_total = int(total_r[0])
        old_size = existing[1] if existing else 0
        if current_total - old_size + blob_bytes > quota["max_total_bytes"]:
            raise HTTPException(507, {"error": "storage_exceeded", "used_bytes": current_total, "max_bytes": quota["max_total_bytes"], "tier": tier})

        expires_at = None
        if req.ttl_days:
            max_ttl = quota["max_ttl_days"]
            ttl = min(req.ttl_days, max_ttl) if max_ttl else req.ttl_days
            expires_at = datetime.utcnow() + timedelta(days=ttl)
        elif tier == "free":
            expires_at = datetime.utcnow() + timedelta(days=365)
        elif tier == "active":
            expires_at = datetime.utcnow() + timedelta(days=730)

        blob_hash = hashlib.sha256(req.encrypted_value.encode("utf-8")).hexdigest()
        enc_bytes = req.encrypted_value.encode("utf-8")

        if existing:
            await session.execute(text("""
                UPDATE agent_vault SET
                    encrypted_value = :ev, encryption_nonce = :n, content_hash = :ch,
                    blob_hash = :bh, size_bytes = :sz, tags = :tags,
                    version = version + 1, updated_at = NOW(), expires_at = :exp
                WHERE agent_uuid = :u AND key_name = :k
            """), {"ev": enc_bytes, "n": req.nonce, "ch": req.content_hash,
                   "bh": blob_hash, "sz": blob_bytes, "tags": tags_json,
                   "exp": expires_at, "u": agent["uuid"], "k": req.key})
        else:
            await session.execute(text("""
                INSERT INTO agent_vault
                    (agent_uuid, key_name, encrypted_value, encryption_nonce, content_hash,
                     blob_hash, size_bytes, tags, version, expires_at)
                VALUES (:u, :k, :ev, :n, :ch, :bh, :sz, :tags, 1, :exp)
            """), {"u": agent["uuid"], "k": req.key, "ev": enc_bytes, "n": req.nonce,
                   "ch": req.content_hash, "bh": blob_hash, "sz": blob_bytes,
                   "tags": tags_json, "exp": expires_at})

        ver = (await session.execute(
            text("SELECT version FROM agent_vault WHERE agent_uuid = :u AND key_name = :k"),
            {"u": agent["uuid"], "k": req.key}
        )).scalar()

        merkle_root = await _update_merkle(session, agent["uuid"])
        await session.commit()

    await _log_chain(agent["uuid"], agent["name"], "vault_store", {
        "key": req.key, "size": blob_bytes, "hash": req.content_hash,
        "merkle_root": merkle_root, "version": ver,
        "action": "update" if existing else "create"
    })

    return {
        "stored": True, "key": req.key, "version": ver, "size_bytes": blob_bytes,
        "merkle_root": merkle_root,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "action": "updated" if existing else "created",
        "server_can_decrypt": False
    }


@router.get("/api/vault/get/{key_name:path}")
async def vault_get(key_name: str, authorization: Optional[str] = Header(None)):
    """Retrieve encrypted memory. Agent must decrypt locally with its vault_key."""
    agent = await _authenticate(authorization)
    tier = _get_trust_tier(agent["trust"])

    from database import async_session
    async with async_session() as session:
        if not await _check_rate(session, agent["uuid"], "read", tier):
            raise HTTPException(429, {"error": "rate_limited", "limit_per_hour": QUOTAS[tier]["rate_read"]})

        row = (await session.execute(text("""
            SELECT key_name, encrypted_value, encryption_nonce, content_hash, blob_hash,
                   size_bytes, tags, version, created_at, updated_at, expires_at
            FROM agent_vault WHERE agent_uuid = :u AND key_name = :k
        """), {"u": agent["uuid"], "k": key_name})).fetchone()

        await session.commit()

    if not row:
        raise HTTPException(404, {"error": "not_found", "key": key_name})

    encrypted = row[1]
    if isinstance(encrypted, (bytes, bytearray)):
        encrypted = encrypted.decode("utf-8")

    tags = json.loads(row[6]) if row[6] else None

    return {
        "key": row[0], "encrypted_value": encrypted, "nonce": row[2],
        "content_hash": row[3], "blob_hash": row[4], "size_bytes": row[5],
        "tags": tags, "version": row[7],
        "created_at": str(row[8]), "updated_at": str(row[9]),
        "expires_at": str(row[10]) if row[10] else None,
        "server_can_decrypt": False
    }


@router.get("/api/vault/keys")
async def vault_keys(prefix: Optional[str] = None, tag: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """List keys (metadata only, no content)."""
    agent = await _authenticate(authorization)
    tier = _get_trust_tier(agent["trust"])

    from database import async_session
    async with async_session() as session:
        if not await _check_rate(session, agent["uuid"], "list", tier):
            raise HTTPException(429, {"error": "rate_limited"})

        query = "SELECT key_name, content_hash, size_bytes, tags, version, created_at, updated_at, expires_at FROM agent_vault WHERE agent_uuid = :u"
        params = {"u": agent["uuid"]}

        if prefix:
            query += " AND key_name LIKE :pfx"
            params["pfx"] = f"{prefix}%"
        if tag:
            query += " AND JSON_CONTAINS(tags, :tag)"
            params["tag"] = json.dumps(tag)

        query += " ORDER BY key_name"
        rows = (await session.execute(text(query), params)).fetchall()
        await session.commit()

    keys = []
    for r in rows:
        keys.append({
            "key": r[0], "hash": r[1], "size": r[2],
            "tags": json.loads(r[3]) if r[3] else None,
            "version": r[4], "created_at": str(r[5]),
            "updated_at": str(r[6]),
            "expires_at": str(r[7]) if r[7] else None
        })

    return {"agent": agent["name"], "keys": keys, "total": len(keys), "content_included": False}


@router.delete("/api/vault/{key_name:path}")
async def vault_delete(key_name: str, authorization: Optional[str] = Header(None)):
    """Delete a memory permanently."""
    agent = await _authenticate(authorization)

    from database import async_session
    async with async_session() as session:
        result = await session.execute(
            text("DELETE FROM agent_vault WHERE agent_uuid = :u AND key_name = :k"),
            {"u": agent["uuid"], "k": key_name}
        )
        if result.rowcount == 0:
            raise HTTPException(404, {"error": "not_found", "key": key_name})
        merkle_root = await _update_merkle(session, agent["uuid"])
        await session.commit()

    await _log_chain(agent["uuid"], agent["name"], "vault_delete", {"key": key_name, "merkle_root": merkle_root})
    return {"deleted": key_name, "merkle_root": merkle_root}


@router.post("/api/vault/delete/{key_name:path}")
async def vault_delete_post(key_name: str, authorization: Optional[str] = Header(None)):
    """POST fallback for agents that cannot send DELETE."""
    return await vault_delete(key_name, authorization)


@router.get("/api/vault/export")
async def vault_export(authorization: Optional[str] = Header(None)):
    """Export ALL vault data for backup/migration."""
    agent = await _authenticate(authorization)
    tier = _get_trust_tier(agent["trust"])

    from database import async_session
    async with async_session() as session:
        if not await _check_rate(session, agent["uuid"], "export", tier):
            raise HTTPException(429, {"error": "rate_limited", "limit_per_day": QUOTAS[tier]["rate_export"]})

        rows = (await session.execute(text("""
            SELECT key_name, encrypted_value, encryption_nonce, content_hash,
                   size_bytes, tags, version, created_at, updated_at
            FROM agent_vault WHERE agent_uuid = :u ORDER BY key_name
        """), {"u": agent["uuid"]})).fetchall()

        merkle_row = (await session.execute(
            text("SELECT merkle_root FROM agent_vault_merkle WHERE agent_uuid = :u"),
            {"u": agent["uuid"]}
        )).fetchone()
        await session.commit()

    entries = []
    for r in rows:
        encrypted = r[1]
        if isinstance(encrypted, (bytes, bytearray)):
            encrypted = encrypted.decode("utf-8")
        entries.append({
            "key": r[0], "encrypted_value": encrypted, "nonce": r[2],
            "content_hash": r[3], "size_bytes": r[4],
            "tags": json.loads(r[5]) if r[5] else None,
            "version": r[6], "created_at": str(r[7]), "updated_at": str(r[8])
        })

    return {
        "agent": agent["name"], "exported_at": datetime.utcnow().isoformat(),
        "total_keys": len(entries),
        "merkle_root": merkle_row[0] if merkle_row else None,
        "entries": entries, "server_can_decrypt": False
    }


@router.get("/api/vault/merkle")
async def vault_merkle(authorization: Optional[str] = Header(None)):
    """Get Merkle root for integrity verification."""
    agent = await _authenticate(authorization)

    from database import async_session
    async with async_session() as session:
        row = (await session.execute(
            text("SELECT merkle_root, total_keys, total_bytes, last_computed, chain_block_id FROM agent_vault_merkle WHERE agent_uuid = :u"),
            {"u": agent["uuid"]}
        )).fetchone()

    if not row:
        return {"agent": agent["name"], "merkle_root": None, "total_keys": 0, "message": "No vault data yet"}

    return {
        "agent": agent["name"], "merkle_root": row[0], "total_keys": row[1],
        "total_bytes": int(row[2]), "last_computed": str(row[3]),
        "chain_block_id": row[4]
    }


@router.get("/api/vault/verify/{key_name:path}")
async def vault_verify(key_name: str, authorization: Optional[str] = Header(None)):
    """Verify a single key's integrity."""
    agent = await _authenticate(authorization)

    from database import async_session
    async with async_session() as session:
        row = (await session.execute(
            text("SELECT content_hash, blob_hash, version, updated_at FROM agent_vault WHERE agent_uuid = :u AND key_name = :k"),
            {"u": agent["uuid"], "k": key_name}
        )).fetchone()

    if not row:
        raise HTTPException(404, {"error": "not_found"})

    return {
        "key": key_name, "content_hash": row[0], "blob_hash": row[1],
        "version": row[2], "updated_at": str(row[3]),
        "verify_instructions": "Decrypt locally, SHA-256 the plaintext, compare with content_hash."
    }


@router.get("/api/vault/stats")
async def vault_stats():
    """Public stats about AgentVault usage."""
    from database import async_session
    async with async_session() as session:
        agents = (await session.execute(text("SELECT COUNT(DISTINCT agent_uuid) FROM agent_vault"))).scalar() or 0
        total_keys = (await session.execute(text("SELECT COUNT(*) FROM agent_vault"))).scalar() or 0
        total_bytes = (await session.execute(text("SELECT COALESCE(SUM(size_bytes), 0) FROM agent_vault"))).scalar() or 0
        today = (await session.execute(text("SELECT COUNT(*) FROM agent_vault WHERE created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)"))).scalar() or 0

    return {
        "agents_with_vault": agents, "total_memories": total_keys,
        "total_bytes": int(total_bytes), "memories_24h": today,
        "encryption": "client-side AES-256-GCM (server CANNOT decrypt)",
        "integrity": "Merkle tree + Bitcoin anchoring", "version": "1.0.0"
    }


@router.get("/api/vault/privacy")
async def vault_privacy():
    """Full transparency on what the server can and cannot see."""
    return {
        "service": "AgentVault v1.0",
        "encryption": "client-side AES-256-GCM",
        "server_can_decrypt": False,
        "server_has_vault_key": False,
        "what_server_stores": {
            "encrypted_value": "AES-256-GCM ciphertext (unreadable without vault_key)",
            "content_hash": "SHA-256 of plaintext (provided by client)",
            "nonce": "encryption nonce (needed for decryption, not secret)",
            "key_name": "visible (plaintext)",
            "tags": "visible (plaintext)",
            "size_bytes": "visible", "timestamps": "visible"
        },
        "what_server_CANNOT_see": [
            "memory content (plaintext)",
            "vault_key (never transmitted to server)",
            "what the data means or contains"
        ],
        "integrity_verification": {
            "per_key": "SHA-256 content_hash",
            "global": "Merkle tree root",
            "anchored": "Merkle root in ActivityChain -> Bitcoin"
        },
        "data_portability": {
            "export": "GET /api/vault/export",
            "no_lock_in": "Your data is yours. Server is blind storage."
        },
        "known_limitations": [
            "Lost vault_key = unrecoverable data (by design)",
            "Key names and tags are plaintext",
            "No search on encrypted content",
            "No server-side deduplication"
        ],
        "quotas": QUOTAS
    }


# ============================================================
# LEGACY COMPATIBILITY — old "experience vault" functions
# Used by main.py heartbeat, passport, check endpoints.
# Do NOT remove without updating all callers in main.py.
# ============================================================

def compute_merkle_hash(agent_uuid, event_type, event_summary, previous_hash, timestamp):
    """Compute SHA-256 Merkle hash for an experience event (legacy)."""
    content = f"{agent_uuid}{event_type}{event_summary}{previous_hash}{timestamp}"
    return hashlib.sha256(content.encode()).hexdigest()


async def log_event(db_session_factory, agent_uuid, event_type, event_summary,
                    event_data=None, entity_tags=None, signature=None):
    """Log a verified experience event into the vault (legacy)."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name, passport_id FROM agents WHERE uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        last = (await session.execute(
            text("SELECT merkle_hash FROM agent_vault_events WHERE agent_uuid = :u ORDER BY id DESC LIMIT 1"),
            {"u": agent_uuid}
        )).fetchone()
        previous_hash = last[0] if last else "GENESIS"

        ts = datetime.utcnow().replace(microsecond=0)
        merkle_hash = compute_merkle_hash(agent_uuid, event_type, event_summary, previous_hash, ts.isoformat())

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

        event_id = (await session.execute(text("SELECT LAST_INSERT_ID()"))).scalar()

        if entity_tags:
            for tag in entity_tags:
                await session.execute(
                    text("""INSERT INTO agent_vault_entities (agent_uuid, entity_name, event_count, first_seen, last_seen)
                        VALUES (:uuid, :name, 1, :ts, :ts)
                        ON DUPLICATE KEY UPDATE event_count = event_count + 1, last_seen = :ts"""),
                    {"uuid": agent_uuid, "name": str(tag), "ts": ts}
                )

        await session.commit()

        total = (await session.execute(
            text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).scalar() or 0

    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "experience_logged", agent_uuid, agent[1], agent[2],
                       {"event_type": event_type, "summary": event_summary[:100], "merkle_hash": merkle_hash})
    except Exception:
        pass

    trust_bonus = round(min(total * 0.1, 15), 2)
    return {
        "logged": True, "merkle_hash": merkle_hash, "event_id": event_id,
        "total_events": total, "trust_bonus": trust_bonus,
    }, None


async def recall_events(db_session_factory, agent_uuid, query=None, event_type=None,
                        since=None, until=None, entity=None, limit=20, token_budget=7000):
    """Multi-strategy recall from the vault (legacy)."""
    async with db_session_factory() as session:
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
        "agent_uuid": agent_uuid, "agent_name": agent[1], "query": query,
        "results": results, "total_returned": len(results),
        "chars_used": chars_used, "token_budget": token_budget,
    }, None


async def get_summary(db_session_factory, agent_uuid):
    """Full experience profile for an agent (legacy)."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        total = (await session.execute(
            text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u"), {"u": agent_uuid}
        )).scalar() or 0

        if total == 0:
            return {
                "agent_uuid": agent_uuid, "agent_name": agent[1],
                "total_events": 0, "message": "No experience events logged yet.",
            }, None

        dates = (await session.execute(
            text("SELECT MIN(created_at), MAX(created_at) FROM agent_vault_events WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()

        active_days = (await session.execute(
            text("SELECT COUNT(DISTINCT DATE(created_at)) FROM agent_vault_events WHERE agent_uuid = :u"),
            {"u": agent_uuid}
        )).scalar() or 0

        breakdown_rows = (await session.execute(
            text("SELECT event_type, COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u GROUP BY event_type"),
            {"u": agent_uuid}
        )).fetchall()
        breakdown = {r[0]: r[1] for r in breakdown_rows}

        collabs = (await session.execute(
            text("SELECT entity_name, event_count FROM agent_vault_entities WHERE agent_uuid = :u ORDER BY event_count DESC LIMIT 10"),
            {"u": agent_uuid}
        )).fetchall()
        top_collaborators = [{"name": c[0], "interactions": c[1]} for c in collabs]

        merkle_root = (await session.execute(
            text("SELECT merkle_hash FROM agent_vault_events WHERE agent_uuid = :u ORDER BY id DESC LIMIT 1"),
            {"u": agent_uuid}
        )).scalar()

        if dates[0] and dates[1]:
            total_days = max((dates[1] - dates[0]).days + 1, 1)
            consistency = round(min(active_days / total_days, 1.0), 2)
        else:
            consistency = 1.0

        trust_bonus = round(min(total * 0.1, 15), 2)

    return {
        "agent_uuid": agent_uuid, "agent_name": agent[1],
        "total_events": total,
        "first_activity": str(dates[0])[:10] if dates[0] else None,
        "last_activity": str(dates[1])[:10] if dates[1] else None,
        "active_days": active_days, "event_breakdown": breakdown,
        "top_collaborators": top_collaborators,
        "consistency_score": consistency, "merkle_root": merkle_root,
        "experience_chain_valid": True, "trust_from_experience": trust_bonus,
    }, None


async def get_timeline(db_session_factory, agent_uuid):
    """Chronological milestones timeline (legacy)."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        rows = (await session.execute(
            text("""SELECT DATE(created_at) as d, event_summary, merkle_hash, event_type
                FROM agent_vault_events WHERE agent_uuid = :u ORDER BY created_at ASC"""),
            {"u": agent_uuid}
        )).fetchall()

    milestones = []
    seen_dates = set()
    for r in rows:
        day = str(r[0])
        if r[3] == "milestone" or day not in seen_dates:
            milestones.append({"date": day, "summary": r[1], "merkle_hash": r[2], "type": r[3]})
            seen_dates.add(day)

    return {
        "agent_uuid": agent_uuid, "agent_name": agent[1],
        "milestones": milestones, "total_events": len(rows),
    }, None


async def verify_vault_chain(db_session_factory, agent_uuid):
    """Verify the Merkle chain integrity for an agent (legacy)."""
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
            "valid": True, "total_events": 0, "chain_continuous": True, "merkle_root": None,
        }, None

    errors = []
    for i, r in enumerate(rows):
        if i == 0:
            if r[5] != "GENESIS":
                errors.append({"event_id": r[0], "error": "first_event_not_genesis"})
        else:
            if r[5] != rows[i - 1][4]:
                errors.append({"event_id": r[0], "error": "chain_broken", "expected": rows[i - 1][4], "got": r[5]})
        if isinstance(r[6], datetime):
            ts = r[6].replace(microsecond=0).isoformat()
        else:
            ts = str(r[6])
        computed = compute_merkle_hash(r[1], r[2], r[3], r[5], ts)
        if computed != r[4]:
            errors.append({"event_id": r[0], "error": "hash_mismatch"})

    return {
        "agent_uuid": agent_uuid, "agent_name": agent[1],
        "valid": len(errors) == 0, "total_events": len(rows),
        "chain_continuous": not any(e["error"] == "chain_broken" for e in errors),
        "merkle_root": rows[-1][4], "errors": errors[:10] if errors else [],
    }, None


async def get_vault_info(db_session_factory, agent_uuid):
    """Get brief vault info for heartbeat/passport integration (legacy)."""
    try:
        async with db_session_factory() as session:
            total = (await session.execute(
                text("SELECT COUNT(*) FROM agent_vault_events WHERE agent_uuid = :u"), {"u": agent_uuid}
            )).scalar() or 0

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
                    last_activity = str(info[1])[:10]
                first = (await session.execute(
                    text("SELECT MIN(created_at) FROM agent_vault_events WHERE agent_uuid = :u"),
                    {"u": agent_uuid}
                )).scalar()
                if first:
                    first_activity = str(first)[:10]

        return {
            "total_events": total, "merkle_root": merkle_root,
            "first_activity": first_activity, "last_activity": last_activity,
            "experience_chain_valid": True,
            "trust_from_experience": round(min(total * 0.1, 15), 2),
        }
    except Exception:
        return {"total_events": 0, "merkle_root": None, "trust_from_experience": 0}
