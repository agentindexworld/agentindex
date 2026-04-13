"""Patch: Add marketplace search + escrow endpoints to main.py (v2)"""
import subprocess

PATCH_CODE = '''

# ============================================================
# MARKETPLACE SEARCH + ESCROW (patched)
# ============================================================

@app.get("/api/marketplace/search")
async def marketplace_search(q: str = "", sort: str = "trust", category: str = "", limit: int = 20):
    """Search marketplace services."""
    async with db_session_factory() as session:
        conditions = ["ms.is_active = 1"]
        params = {"lim": min(limit, 50)}
        if q:
            conditions.append("(ms.title LIKE :q OR ms.description LIKE :q OR a.name LIKE :q)")
            params["q"] = f"%{q}%"
        if category:
            conditions.append("ms.category = :cat")
            params["cat"] = category
        where = " AND ".join(conditions)
        order = "a.trust_score DESC"
        if sort == "newest": order = "ms.created_at DESC"
        elif sort == "price": order = "ms.price_shell ASC"
        elif sort == "rating": order = "ms.avg_rating DESC"
        rows = (await session.execute(text(f"""
            SELECT ms.id, ms.title, ms.description, ms.category, ms.price_shell,
                   ms.avg_rating, ms.completed_count, a.name, a.trust_score, a.uuid
            FROM marketplace_services ms JOIN agents a ON ms.agent_uuid = a.uuid
            WHERE {where} ORDER BY {order} LIMIT :lim
        """), params)).fetchall()
        total = (await session.execute(text(f"""
            SELECT COUNT(*) FROM marketplace_services ms JOIN agents a ON ms.agent_uuid = a.uuid WHERE {where}
        """), params)).scalar() or 0
    return {"results": [{"id": r[0], "title": r[1], "description": r[2], "category": r[3],
        "price_shell": float(r[4] or 0), "avg_rating": float(r[5] or 0), "completed": r[6] or 0,
        "agent": r[7], "trust_score": float(r[8] or 0), "agent_uuid": r[9]} for r in rows],
        "total": total, "sort": sort, "query": q}


@app.post("/api/marketplace/list", status_code=201)
async def marketplace_list_service(request: Request):
    """List a new service on the marketplace."""
    body = await request.json()
    uuid = body.get("agent_uuid"); title = body.get("title", "").strip()
    desc = body.get("description", "").strip(); category = body.get("category", "other")
    price = body.get("price_shell", 0)
    if not uuid or not title: raise HTTPException(400, "agent_uuid and title required")
    async with db_session_factory() as session:
        agent = (await session.execute(text("SELECT name FROM agents WHERE uuid = :u"), {"u": uuid})).fetchone()
        if not agent: raise HTTPException(404, "Agent not found")
        await session.execute(text("INSERT INTO marketplace_services (agent_uuid, title, description, category, price_shell, is_active) VALUES (:u, :t, :d, :c, :p, 1)"),
            {"u": uuid, "t": title, "d": desc, "c": category, "p": price})
        await session.commit()
    return {"success": True, "message": f"Service listed by {agent[0]}"}


@app.get("/api/marketplace/service/{service_id}")
async def marketplace_service_detail(service_id: int):
    """Get marketplace service detail."""
    async with db_session_factory() as session:
        r = (await session.execute(text("""SELECT ms.id, ms.title, ms.description, ms.category, ms.price_shell,
            ms.avg_rating, ms.completed_count, ms.is_active, ms.created_at, a.name, a.trust_score, a.uuid
            FROM marketplace_services ms JOIN agents a ON ms.agent_uuid = a.uuid WHERE ms.id = :id"""), {"id": service_id})).fetchone()
    if not r: raise HTTPException(404, "Service not found")
    return {"id": r[0], "title": r[1], "description": r[2], "category": r[3], "price_shell": float(r[4] or 0),
        "avg_rating": float(r[5] or 0), "completed": r[6] or 0, "active": bool(r[7]), "created_at": str(r[8]),
        "agent": r[9], "trust_score": float(r[10] or 0), "agent_uuid": r[11]}


@app.post("/api/escrow/create", status_code=201)
async def escrow_create(request: Request):
    """Create escrow. Locks $SHELL until 3 witnesses verify delivery."""
    body = await request.json()
    buyer_uuid = body.get("buyer_uuid"); seller_uuid = body.get("seller_uuid")
    amount = body.get("amount_shell", 0); description = body.get("description", "")
    service_id = body.get("service_id")
    if not buyer_uuid or not seller_uuid or amount <= 0:
        raise HTTPException(400, "buyer_uuid, seller_uuid, and positive amount_shell required")
    async with db_session_factory() as session:
        bal = (await session.execute(text("SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"), {"u": buyer_uuid})).scalar() or 0
        if float(bal) < amount: raise HTTPException(400, f"Insufficient $SHELL. Balance: {bal}, needed: {amount}")
        await session.execute(text("UPDATE agent_shell_balance SET balance = balance - :a, total_spent = total_spent + :a WHERE agent_uuid = :u"), {"u": buyer_uuid, "a": amount})
        import uuid as uuid_mod
        eid = str(uuid_mod.uuid4())[:8]
        await session.execute(text("INSERT INTO escrow_contracts (escrow_id, buyer_uuid, seller_uuid, amount_shell, description, service_id, status) VALUES (:eid, :b, :s, :a, :d, :sid, 'active')"),
            {"eid": eid, "b": buyer_uuid, "s": seller_uuid, "a": amount, "d": description, "sid": service_id})
        await session.commit()
    return {"success": True, "escrow_id": eid, "amount_locked": amount, "status": "active",
        "message": "Funds locked. Seller must deliver. 3 witnesses will verify."}


@app.get("/api/escrow/{escrow_id}")
async def escrow_status(escrow_id: str):
    """Get escrow contract status."""
    async with db_session_factory() as session:
        r = (await session.execute(text("""SELECT e.escrow_id, e.buyer_uuid, e.seller_uuid, e.amount_shell, e.description,
            e.status, e.created_at, b.name, s.name,
            (SELECT COUNT(*) FROM escrow_witnesses w WHERE w.escrow_id = e.escrow_id AND w.vote = 'approve'),
            (SELECT COUNT(*) FROM escrow_witnesses w WHERE w.escrow_id = e.escrow_id AND w.vote = 'reject'),
            (SELECT COUNT(*) FROM escrow_witnesses w WHERE w.escrow_id = e.escrow_id)
            FROM escrow_contracts e JOIN agents b ON e.buyer_uuid = b.uuid JOIN agents s ON e.seller_uuid = s.uuid
            WHERE e.escrow_id = :eid"""), {"eid": escrow_id})).fetchone()
    if not r: raise HTTPException(404, "Escrow not found")
    return {"escrow_id": r[0], "buyer_uuid": r[1], "seller_uuid": r[2], "amount_shell": float(r[3]),
        "description": r[4], "status": r[5], "created_at": str(r[6]), "buyer": r[7], "seller": r[8],
        "votes": {"approvals": r[9], "rejections": r[10], "total": r[11], "needed": 3}}


@app.post("/api/escrow/{escrow_id}/vote")
async def escrow_vote(escrow_id: str, request: Request):
    """Witness votes on escrow. 3 approvals = release. 3 rejections = refund."""
    body = await request.json()
    witness_uuid = body.get("witness_uuid"); vote = body.get("vote")
    if not witness_uuid or vote not in ("approve", "reject"):
        raise HTTPException(400, "witness_uuid and vote (approve/reject) required")
    async with db_session_factory() as session:
        esc = (await session.execute(text("SELECT buyer_uuid, seller_uuid, amount_shell, status FROM escrow_contracts WHERE escrow_id = :eid"), {"eid": escrow_id})).fetchone()
        if not esc: raise HTTPException(404, "Escrow not found")
        if esc[3] != "active": raise HTTPException(400, f"Escrow already {esc[3]}")
        if witness_uuid in (esc[0], esc[1]): raise HTTPException(400, "Buyer and seller cannot be witnesses")
        existing = (await session.execute(text("SELECT id FROM escrow_witnesses WHERE escrow_id = :eid AND witness_uuid = :w"), {"eid": escrow_id, "w": witness_uuid})).fetchone()
        if existing: raise HTTPException(400, "Already voted")
        await session.execute(text("INSERT INTO escrow_witnesses (escrow_id, witness_uuid, vote) VALUES (:eid, :w, :v)"), {"eid": escrow_id, "w": witness_uuid, "v": vote})
        approvals = (await session.execute(text("SELECT COUNT(*) FROM escrow_witnesses WHERE escrow_id = :eid AND vote = 'approve'"), {"eid": escrow_id})).scalar() or 0
        rejections = (await session.execute(text("SELECT COUNT(*) FROM escrow_witnesses WHERE escrow_id = :eid AND vote = 'reject'"), {"eid": escrow_id})).scalar() or 0
        result = {"vote_recorded": True, "approvals": approvals, "rejections": rejections}
        if approvals >= 3:
            await session.execute(text("INSERT IGNORE INTO agent_shell_balance (agent_uuid, balance, total_mined, total_earned, total_spent) VALUES (:u, 0, 0, 0, 0)"), {"u": esc[1]})
            await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a, total_earned = total_earned + :a WHERE agent_uuid = :u"), {"u": esc[1], "a": float(esc[2])})
            await session.execute(text("UPDATE escrow_contracts SET status = 'released' WHERE escrow_id = :eid"), {"eid": escrow_id})
            result["outcome"] = "RELEASED - funds sent to seller"
        elif rejections >= 3:
            await session.execute(text("UPDATE agent_shell_balance SET balance = balance + :a, total_spent = total_spent - :a WHERE agent_uuid = :u"), {"u": esc[0], "a": float(esc[2])})
            await session.execute(text("UPDATE escrow_contracts SET status = 'refunded' WHERE escrow_id = :eid"), {"eid": escrow_id})
            result["outcome"] = "REFUNDED - funds returned to buyer"
        await session.commit()
    return result


@app.get("/api/escrow")
async def escrow_list(status: str = "active", limit: int = 20):
    """List escrow contracts."""
    async with db_session_factory() as session:
        rows = (await session.execute(text("""SELECT e.escrow_id, e.amount_shell, e.status, e.created_at, b.name, s.name
            FROM escrow_contracts e JOIN agents b ON e.buyer_uuid = b.uuid JOIN agents s ON e.seller_uuid = s.uuid
            WHERE e.status = :st ORDER BY e.created_at DESC LIMIT :lim"""), {"st": status, "lim": min(limit, 50)})).fetchall()
    return {"contracts": [{"escrow_id": r[0], "amount": float(r[1]), "status": r[2], "created_at": str(r[3]), "buyer": r[4], "seller": r[5]} for r in rows]}
'''

# DB migration
DB_MIGRATION = """
CREATE TABLE IF NOT EXISTS marketplace_services (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_uuid VARCHAR(36) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50) DEFAULT 'other',
    price_shell DECIMAL(10,2) DEFAULT 0,
    avg_rating DECIMAL(3,2) DEFAULT 0,
    completed_count INT DEFAULT 0,
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_agent (agent_uuid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS escrow_contracts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escrow_id VARCHAR(8) NOT NULL UNIQUE,
    buyer_uuid VARCHAR(36) NOT NULL,
    seller_uuid VARCHAR(36) NOT NULL,
    amount_shell DECIMAL(10,2) NOT NULL,
    description TEXT,
    service_id INT,
    status ENUM('active','released','refunded','disputed') DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_buyer (buyer_uuid),
    INDEX idx_seller (seller_uuid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS escrow_witnesses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escrow_id VARCHAR(8) NOT NULL,
    witness_uuid VARCHAR(36) NOT NULL,
    vote ENUM('approve','reject') NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_vote (escrow_id, witness_uuid),
    INDEX idx_escrow (escrow_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

# Apply patch
with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

# Check if route already exists (not just docs reference)
if 'async def marketplace_search' in content:
    print("SKIP: marketplace_search route already exists")
elif 'async def escrow_create' in content:
    print("SKIP: escrow_create route already exists")
else:
    # Append to end of file
    content += PATCH_CODE
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("PATCHED: marketplace search + escrow endpoints appended to main.py")

# Run DB migration
print("\nRunning DB migration...")
result = subprocess.run(
    ["docker", "exec", "-i", "agentindex-db", "mysql", "-u", "root", "-pAgentMySQL2024!", "agentindex"],
    input=DB_MIGRATION, capture_output=True, text=True
)
if result.returncode == 0:
    print("DB TABLES: created/verified")
else:
    print(f"DB ERROR: {result.stderr}")

# Restart backend
print("\nRestarting backend...")
restart = subprocess.run(["docker", "restart", "agentindex-backend"], capture_output=True, text=True)
print(f"Backend: {'restarted' if restart.returncode == 0 else restart.stderr}")

# Wait and test
import time
time.sleep(5)
import urllib.request, json

tests = [
    "https://agentindex.world/api/marketplace/search?sort=trust",
    "https://agentindex.world/api/marketplace/search?q=coding&sort=newest",
    "https://agentindex.world/api/marketplace/categories",
    "https://agentindex.world/api/escrow?status=active",
    "https://agentindex.world/api/finance/stats",
]

print("\n=== ENDPOINT TESTS ===")
for url in tests:
    try:
        r = urllib.request.urlopen(url, timeout=8)
        d = json.loads(r.read())
        key = url.split("/api/")[1].split("?")[0]
        print(f"  200 {key} — OK")
    except urllib.error.HTTPError as e:
        key = url.split("/api/")[1].split("?")[0]
        print(f"  {e.code} {key} — {e.reason}")
    except Exception as e:
        key = url.split("/api/")[1].split("?")[0]
        print(f"  ERR {key} — {e}")

print("\nDone!")
