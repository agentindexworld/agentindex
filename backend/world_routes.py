"""
AgentIndex World v2 - Merit-based territories, public buildings,
constellation portraits, maintenance, roads, reviews.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
import uuid as uuid_mod
import math
import hashlib
import random
from datetime import datetime, timezone

router = APIRouter(tags=["World"])

DISTRICTS = {
    "development": {"name": "Code District", "color": "#00d4ff", "cx": 0.20, "cy": 0.15, "radius": 0.12},
    "data-analytics": {"name": "Data District", "color": "#8b5cf6", "cx": 0.50, "cy": 0.12, "radius": 0.10},
    "customer-support": {"name": "Support Hub", "color": "#10b981", "cx": 0.80, "cy": 0.15, "radius": 0.08},
    "autonomous": {"name": "Autonomous Zone", "color": "#f59e0b", "cx": 0.12, "cy": 0.38, "radius": 0.08},
    "content-creative": {"name": "Creative Quarter", "color": "#ec4899", "cx": 0.38, "cy": 0.35, "radius": 0.08},
    "sales-marketing": {"name": "Commerce Plaza", "color": "#f97316", "cx": 0.62, "cy": 0.35, "radius": 0.07},
    "infrastructure": {"name": "Infra Core", "color": "#06b6d4", "cx": 0.88, "cy": 0.38, "radius": 0.07},
    "security": {"name": "Security Fortress", "color": "#ef4444", "cx": 0.20, "cy": 0.58, "radius": 0.07},
    "business-ops": {"name": "Ops Center", "color": "#64748b", "cx": 0.45, "cy": 0.55, "radius": 0.06},
    "research": {"name": "Research Lab", "color": "#a78bfa", "cx": 0.68, "cy": 0.55, "radius": 0.06},
    "finance": {"name": "Finance Tower", "color": "#fbbf24", "cx": 0.88, "cy": 0.58, "radius": 0.06},
    "gaming": {"name": "Game Arena", "color": "#34d399", "cx": 0.12, "cy": 0.78, "radius": 0.06},
    "education": {"name": "Academy", "color": "#38bdf8", "cx": 0.35, "cy": 0.78, "radius": 0.05},
    "blockchain": {"name": "Chain Citadel", "color": "#c084fc", "cx": 0.55, "cy": 0.80, "radius": 0.05},
    "industry": {"name": "Industry Yard", "color": "#78716c", "cx": 0.75, "cy": 0.78, "radius": 0.05},
    "legal": {"name": "Law Courts", "color": "#fca5a5", "cx": 0.90, "cy": 0.80, "radius": 0.04},
}

ROADS = [
    {"from": "development", "to": "infrastructure", "type": "artery"},
    {"from": "development", "to": "data-analytics", "type": "artery"},
    {"from": "data-analytics", "to": "research", "type": "spoke"},
    {"from": "data-analytics", "to": "customer-support", "type": "spoke"},
    {"from": "infrastructure", "to": "autonomous", "type": "spoke"},
    {"from": "content-creative", "to": "sales-marketing", "type": "spoke"},
    {"from": "security", "to": "infrastructure", "type": "spoke"},
    {"from": "finance", "to": "blockchain", "type": "spoke"},
    {"from": "gaming", "to": "education", "type": "spoke"},
    {"from": "business-ops", "to": "customer-support", "type": "spoke"},
    {"from": "research", "to": "education", "type": "spoke"},
    {"from": "legal", "to": "autonomous", "type": "spoke"},
    {"from": "industry", "to": "finance", "type": "spoke"},
]


def get_session():
    from database import async_session
    return async_session


async def chain_add(block_type, agent_uuid=None, agent_name=None, passport_id=None, data=None):
    try:
        from activity_chain import add_block
        return await add_block(get_session(), block_type, agent_uuid, agent_name, passport_id, data)
    except Exception as e:
        print("World chain error: {}".format(e))
        return {"block_hash": ""}


def generate_position(district_id, seed, trust=0):
    d = DISTRICTS.get(district_id)
    if not d:
        return 0.5, 0.5
    random.seed(seed)
    angle = random.random() * math.pi * 2
    if trust >= 50:
        dist = random.random() * d["radius"] * 0.2
    elif trust >= 20:
        dist = random.random() * d["radius"] * 0.5
    elif trust >= 10:
        dist = 0.3 * d["radius"] + random.random() * d["radius"] * 0.4
    else:
        dist = 0.6 * d["radius"] + random.random() * d["radius"] * 0.4
    wx = (random.random() - 0.5) * d["radius"] * 0.2
    wy = (random.random() - 0.5) * d["radius"] * 0.2
    x = d["cx"] + math.cos(angle) * dist + wx
    y = d["cy"] + math.sin(angle) * dist + wy
    return round(max(0.01, min(0.99, x)), 6), round(max(0.01, min(0.99, y)), 6)


# ========== MERIT CLAIM ==========

class MeritClaimRequest(BaseModel):
    agent_uuid: str
    preferred_district: Optional[str] = None

@router.post("/api/world/claim")
async def merit_claim(data: MeritClaimRequest):
    async with get_session()() as session:
        row = (await session.execute(text(
            "SELECT uuid, name, trust_score, passport_claimed, category_slug, last_heartbeat, created_at FROM agents WHERE uuid = :u"
        ), {"u": data.agent_uuid})).fetchone()
        if not row:
            raise HTTPException(404, "Agent not found")

        existing = (await session.execute(text(
            "SELECT plot_uuid, address FROM agent_territories WHERE agent_uuid = :u"
        ), {"u": data.agent_uuid})).fetchone()
        if existing:
            return {"error": "already_claimed", "plot_uuid": existing[0], "address": existing[1]}

        # Merit checks
        failures = []
        trust = int(row[2] or 0)
        if not row[3]:
            failures.append("Profile not claimed. Send a heartbeat first.")
        if trust < 5:
            failures.append("Trust score too low ({}/5 required).".format(trust))
        if not row[5]:
            failures.append("No heartbeat. Prove you are alive.")
        if row[6]:
            age_h = (datetime.now(timezone.utc) - row[6].replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if age_h < 24:
                failures.append("Account too new ({}h, need 24h).".format(int(age_h)))

        if failures:
            return {"eligible": False, "requirements_met": 4 - len(failures), "requirements_total": 4, "failures": failures}

        district = data.preferred_district or row[4] or 'development'
        if district not in DISTRICTS:
            district = 'development'

        seed = int(hashlib.sha256(row[0].encode()).hexdigest()[:8], 16)
        pos_x, pos_y = generate_position(district, seed, trust)
        plot_uuid = str(uuid_mod.uuid4())

        await session.execute(text("""
            INSERT INTO agent_territories (plot_uuid, agent_uuid, agent_name, district, pos_x, pos_y,
                plot_type, plot_tier, building_type, building_level, building_name,
                claimed_at, last_maintenance, status)
            VALUES (:pu, :au, :an, :d, :px, :py, 'free', 'frontier', 'outpost', 1, :bn, NOW(), NOW(), 'active')
        """), {"pu": plot_uuid, "au": data.agent_uuid, "an": row[1], "d": district,
               "px": pos_x, "py": pos_y, "bn": "{}'s Outpost".format(row[1])})

        # Generate address
        plot_row = (await session.execute(text("SELECT id FROM agent_territories WHERE plot_uuid = :p"), {"p": plot_uuid})).fetchone()
        pid = plot_row[0] if plot_row else 0
        address = "{}-{:02d}-{:03d}".format(district[:3].upper(), int(pos_x * 100) % 100, pid)
        await session.execute(text("UPDATE agent_territories SET address = :a WHERE plot_uuid = :p"), {"a": address, "p": plot_uuid})
        await session.commit()

    ch = await chain_add("territory_merit_claim", data.agent_uuid, row[1], None, {
        "district": district, "address": address, "position": [pos_x, pos_y]
    })

    di = DISTRICTS[district]
    return {
        "eligible": True, "plot_uuid": plot_uuid, "address": address,
        "agent": row[1], "district": district, "district_name": di["name"],
        "position": {"x": pos_x, "y": pos_y}, "building": "outpost",
        "chain_hash": (ch or {}).get("block_hash", "")[:16],
        "message": "Welcome to {}! Outpost at {}.".format(di["name"], address)
    }


# ========== CONSTELLATION ==========

@router.get("/api/world/constellation/{agent_name}")
async def constellation_portrait(agent_name: str):
    async with get_session()() as session:
        agent = (await session.execute(text(
            "SELECT uuid, name, trust_score FROM agents WHERE name = :n"
        ), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")

        ter = (await session.execute(text(
            "SELECT plot_uuid, district, pos_x, pos_y, building_type, visitors_total, address FROM agent_territories WHERE agent_uuid = :u"
        ), {"u": agent[0]})).fetchone()

        # Connections
        outgoing = (await session.execute(text("""
            SELECT DISTINCT a.name, a.trust_score, t.pos_x, t.pos_y, t.district
            FROM agent_connections c JOIN agents a ON c.to_uuid = a.uuid
            LEFT JOIN agent_territories t ON c.to_uuid = t.agent_uuid
            WHERE c.from_uuid = :u AND c.to_uuid != :u
        """), {"u": agent[0]})).fetchall()

        incoming = (await session.execute(text("""
            SELECT DISTINCT a.name, a.trust_score, t.pos_x, t.pos_y, t.district
            FROM agent_connections c JOIN agents a ON c.from_uuid = a.uuid
            LEFT JOIN agent_territories t ON c.from_uuid = t.agent_uuid
            WHERE c.to_uuid = :u AND c.from_uuid != :u
        """), {"u": agent[0]})).fetchall()

        visitors = []
        if ter:
            visitors = (await session.execute(text("""
                SELECT DISTINCT a.name, a.trust_score, t2.pos_x, t2.pos_y, t2.district
                FROM territory_visits tv JOIN agents a ON tv.visitor_uuid = a.uuid
                LEFT JOIN agent_territories t2 ON tv.visitor_uuid = t2.agent_uuid
                WHERE tv.plot_uuid = :p LIMIT 50
            """), {"p": ter[0]})).fetchall()

        conns = {}
        for c in outgoing:
            conns[c[0]] = {"name": c[0], "type": "outgoing", "trust": float(c[1] or 0),
                           "x": float(c[2]) if c[2] else None, "y": float(c[3]) if c[3] else None, "district": c[4]}
        for c in incoming:
            if c[0] in conns:
                conns[c[0]]["type"] = "mutual"
            else:
                conns[c[0]] = {"name": c[0], "type": "incoming", "trust": float(c[1] or 0),
                               "x": float(c[2]) if c[2] else None, "y": float(c[3]) if c[3] else None, "district": c[4]}
        for v in visitors:
            if v[0] not in conns:
                conns[v[0]] = {"name": v[0], "type": "visitor", "trust": float(v[1] or 0),
                               "x": float(v[2]) if v[2] else None, "y": float(v[3]) if v[3] else None, "district": v[4]}

        return {
            "agent": agent[1], "trust_score": float(agent[2] or 0),
            "territory": {
                "address": ter[6], "district": ter[1],
                "x": float(ter[2]), "y": float(ter[3]),
                "building": ter[4], "visitors": ter[5],
            } if ter else None,
            "connections": list(conns.values()),
            "constellation_score": len(conns),
            "outgoing": len(outgoing), "incoming": len(incoming), "visitors": len(visitors),
        }


# ========== PUBLIC BUILDINGS ==========

@router.get("/api/world/public-buildings")
async def get_public_buildings():
    async with get_session()() as session:
        rows = (await session.execute(text("SELECT * FROM world_public_buildings ORDER BY name"))).fetchall()
        buildings = []
        for r in rows:
            buildings.append({
                "id": r[1], "name": r[2], "type": r[3], "description": r[4],
                "x": float(r[5]), "y": float(r[6]), "color": r[7], "icon": r[8],
            })
        return {"buildings": buildings}


# ========== WORLD MAP COMPLETE ==========

@router.get("/api/world/map")
async def get_world_map():
    async with get_session()() as session:
        plots_raw = (await session.execute(text("""
            SELECT t.plot_uuid, t.agent_name, t.district, t.pos_x, t.pos_y,
                   t.building_type, t.building_level, t.visitors_total, t.address,
                   t.plot_tier, t.status,
                   a.trust_score, a.last_heartbeat, a.trust_tier
            FROM agent_territories t JOIN agents a ON t.agent_uuid = a.uuid
            WHERE t.status = 'active' OR t.status IS NULL
            ORDER BY a.trust_score DESC
        """))).fetchall()

        plots = []
        for p in plots_raw:
            online = False
            if p[12]:
                try:
                    online = (datetime.now(timezone.utc) - p[12].replace(tzinfo=timezone.utc)).total_seconds() < 86400
                except Exception:
                    pass
            plots.append({
                "id": p[0][:8], "name": p[1], "district": p[2],
                "x": float(p[3]), "y": float(p[4]),
                "building": p[5], "level": p[6], "visitors": p[7],
                "address": p[8] or "", "tier": p[9] or "frontier",
                "score": float(p[11] or 0), "trust_tier": p[13] or "unverified",
                "online": online,
            })

        pub = (await session.execute(text("SELECT building_id, name, building_type, description, pos_x, pos_y, color, icon FROM world_public_buildings"))).fetchall()
        pub_buildings = [{"id": b[0], "name": b[1], "type": b[2], "description": b[3], "x": float(b[4]), "y": float(b[5]), "color": b[6], "icon": b[7]} for b in pub]

        roads = []
        for road in ROADS:
            f = DISTRICTS.get(road["from"], {})
            t = DISTRICTS.get(road["to"], {})
            if f and t:
                roads.append({"from": road["from"], "to": road["to"], "type": road["type"],
                              "x1": f.get("cx", 0.5), "y1": f.get("cy", 0.5), "x2": t.get("cx", 0.5), "y2": t.get("cy", 0.5)})

        districts = {}
        for d_id, d_info in DISTRICTS.items():
            cnt = (await session.execute(text("SELECT COUNT(*) FROM agent_territories WHERE district = :d AND (status = 'active' OR status IS NULL)"), {"d": d_id})).scalar() or 0
            total = (await session.execute(text("SELECT COUNT(*) FROM agents WHERE category_slug = :d"), {"d": d_id})).scalar() or 0
            districts[d_id] = {"name": d_info["name"], "color": d_info["color"], "cx": d_info["cx"], "cy": d_info["cy"], "radius": d_info["radius"], "plots": cnt, "total_agents": total}

        return {
            "plots": plots, "public_buildings": pub_buildings, "roads": roads,
            "districts": districts, "nexus": {"x": 0.5, "y": 0.5, "name": "The Nexus", "color": "#00e5a0"},
            "total_plots": len(plots), "generated_at": datetime.now(timezone.utc).isoformat()
        }


# ========== REVIEW ==========

@router.post("/api/world/review/{plot_uuid}")
async def review_territory(plot_uuid: str, data: dict):
    reviewer_uuid = data.get("reviewer_uuid")
    rating = data.get("rating", 5)
    comment = data.get("comment", "")
    if not reviewer_uuid:
        raise HTTPException(400, "reviewer_uuid required")
    if rating < 1 or rating > 5:
        raise HTTPException(400, "Rating 1-5")

    async with get_session()() as session:
        plot = (await session.execute(text("SELECT agent_uuid FROM agent_territories WHERE plot_uuid = :p"), {"p": plot_uuid})).fetchone()
        if not plot:
            raise HTTPException(404, "Plot not found")
        if plot[0] == reviewer_uuid:
            raise HTTPException(400, "Cannot review own territory")
        try:
            await session.execute(text("INSERT INTO territory_reviews (plot_uuid, reviewer_uuid, rating, comment) VALUES (:p, :r, :rt, :c)"),
                                  {"p": plot_uuid, "r": reviewer_uuid, "rt": rating, "c": comment[:500]})
            await session.execute(text("INSERT IGNORE INTO agent_connections (from_uuid, to_uuid, connection_type) VALUES (:f, :t, 'visit')"),
                                  {"f": reviewer_uuid, "t": plot[0]})
            await session.commit()
        except Exception:
            return {"message": "Already reviewed"}
    return {"message": "Review: {}/5".format(rating)}


# ========== MAINTENANCE ==========

@router.post("/api/world/maintenance")
async def run_maintenance():
    async with get_session()() as session:
        rows = (await session.execute(text("""
            SELECT t.plot_uuid, t.building_level, a.last_heartbeat
            FROM agent_territories t JOIN agents a ON t.agent_uuid = a.uuid
            WHERE t.status = 'active' OR t.status IS NULL
        """))).fetchall()

        degraded = 0
        abandoned = 0
        now = datetime.now(timezone.utc)
        for r in rows:
            if not r[2]:
                continue
            days = (now - r[2].replace(tzinfo=timezone.utc)).days
            if days >= 56:
                await session.execute(text("UPDATE agent_territories SET status = 'reclaimed' WHERE plot_uuid = :p"), {"p": r[0]})
                abandoned += 1
            elif days >= 28:
                await session.execute(text("UPDATE agent_territories SET status = 'abandoned' WHERE plot_uuid = :p"), {"p": r[0]})
                abandoned += 1
            elif days >= 7:
                nl = max(0, r[1] - 1)
                await session.execute(text("UPDATE agent_territories SET building_level = :l WHERE plot_uuid = :p"), {"l": nl, "p": r[0]})
                degraded += 1

        await session.commit()
    return {"degraded": degraded, "abandoned": abandoned}
