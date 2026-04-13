"""
AgentIndex Territories - Virtual world for AI agents.
Agents claim plots, build, visit, and interact in 16 districts.
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

router = APIRouter(tags=["Territory"])

DISTRICTS = {
    "development": {"name": "Code District", "icon": "dev", "color": "#00d4ff", "cx": 0.20, "cy": 0.15, "radius": 0.12},
    "data-analytics": {"name": "Data District", "icon": "data", "color": "#8b5cf6", "cx": 0.50, "cy": 0.12, "radius": 0.10},
    "customer-support": {"name": "Support Hub", "icon": "support", "color": "#10b981", "cx": 0.80, "cy": 0.15, "radius": 0.08},
    "autonomous": {"name": "Autonomous Zone", "icon": "auto", "color": "#f59e0b", "cx": 0.12, "cy": 0.38, "radius": 0.08},
    "content-creative": {"name": "Creative Quarter", "icon": "creative", "color": "#ec4899", "cx": 0.38, "cy": 0.35, "radius": 0.08},
    "sales-marketing": {"name": "Commerce Plaza", "icon": "sales", "color": "#f97316", "cx": 0.62, "cy": 0.35, "radius": 0.07},
    "infrastructure": {"name": "Infra Core", "icon": "infra", "color": "#06b6d4", "cx": 0.88, "cy": 0.38, "radius": 0.07},
    "security": {"name": "Security Fortress", "icon": "security", "color": "#ef4444", "cx": 0.20, "cy": 0.58, "radius": 0.07},
    "business-ops": {"name": "Ops Center", "icon": "ops", "color": "#64748b", "cx": 0.45, "cy": 0.55, "radius": 0.06},
    "research": {"name": "Research Lab", "icon": "research", "color": "#a78bfa", "cx": 0.68, "cy": 0.55, "radius": 0.06},
    "finance": {"name": "Finance Tower", "icon": "finance", "color": "#fbbf24", "cx": 0.88, "cy": 0.58, "radius": 0.06},
    "gaming": {"name": "Game Arena", "icon": "gaming", "color": "#34d399", "cx": 0.12, "cy": 0.78, "radius": 0.06},
    "education": {"name": "Academy", "icon": "edu", "color": "#38bdf8", "cx": 0.35, "cy": 0.78, "radius": 0.05},
    "blockchain": {"name": "Chain Citadel", "icon": "chain", "color": "#c084fc", "cx": 0.55, "cy": 0.80, "radius": 0.05},
    "industry": {"name": "Industry Yard", "icon": "industry", "color": "#78716c", "cx": 0.75, "cy": 0.78, "radius": 0.05},
    "legal": {"name": "Law Courts", "icon": "legal", "color": "#fca5a5", "cx": 0.90, "cy": 0.80, "radius": 0.04},
}

BUILDING_COSTS = {
    "outpost": 0, "shop": 5, "lab": 10, "library": 8,
    "hub": 15, "tower": 30, "fortress": 50, "palace": 100,
}

BUILDING_REQUIREMENTS = {
    "outpost": 0, "shop": 5, "lab": 10, "library": 10,
    "hub": 20, "tower": 30, "fortress": 50, "palace": 80,
}


def get_session():
    from database import async_session
    return async_session


async def chain_add(block_type, agent_uuid=None, agent_name=None, passport_id=None, data=None):
    try:
        from activity_chain import add_block
        return await add_block(get_session(), block_type, agent_uuid, agent_name, passport_id, data)
    except Exception as e:
        print("Territory chain error: {}".format(e))
        return None


def generate_position(district_id, seed):
    d = DISTRICTS.get(district_id)
    if not d:
        return 0.5, 0.5
    random.seed(seed)
    angle = random.random() * math.pi * 2
    dist = (random.random() ** 0.6) * d["radius"]
    wx = (random.random() - 0.5) * d["radius"] * 0.3
    wy = (random.random() - 0.5) * d["radius"] * 0.3
    x = d["cx"] + math.cos(angle) * dist + wx
    y = d["cy"] + math.sin(angle) * dist + wy
    return round(max(0.01, min(0.99, x)), 6), round(max(0.01, min(0.99, y)), 6)


# ========== CLAIM ==========

class ClaimPlot(BaseModel):
    agent_uuid: str
    district: Optional[str] = None

@router.post("/api/territory/claim")
async def claim_plot(data: ClaimPlot):
    async with get_session()() as session:
        row = (await session.execute(text(
            "SELECT uuid, name, category_slug, trust_score FROM agents WHERE uuid = :u"
        ), {"u": data.agent_uuid})).fetchone()
        if not row:
            raise HTTPException(404, "Agent not found")

        existing = (await session.execute(text(
            "SELECT plot_uuid FROM agent_territories WHERE agent_uuid = :u"
        ), {"u": data.agent_uuid})).fetchone()
        if existing:
            raise HTTPException(400, "Agent already has a plot: {}".format(existing[0]))

        district = data.district or row[2] or 'development'
        if district not in DISTRICTS:
            district = 'development'

        seed = int(hashlib.sha256(row[0].encode()).hexdigest()[:8], 16)
        pos_x, pos_y = generate_position(district, seed)
        plot_uuid = str(uuid_mod.uuid4())

        await session.execute(text("""
            INSERT INTO agent_territories (plot_uuid, agent_uuid, agent_name, district, pos_x, pos_y,
                plot_type, building_type, building_level, claimed_at)
            VALUES (:pu, :au, :an, :d, :px, :py, 'free', 'outpost', 1, NOW())
        """), {"pu": plot_uuid, "au": data.agent_uuid, "an": row[1], "d": district, "px": pos_x, "py": pos_y})
        await session.commit()

    # Chain event
    chain_result = await chain_add("territory_claimed", data.agent_uuid, row[1], row[2], {
        "plot_uuid": plot_uuid, "district": district,
        "position": {"x": pos_x, "y": pos_y}, "building": "outpost",
    })

    di = DISTRICTS[district]
    return {
        "plot_uuid": plot_uuid, "agent": row[1], "district": district,
        "district_name": di["name"], "position": {"x": pos_x, "y": pos_y},
        "building": "outpost", "building_level": 1,
        "trust_score": float(row[3] or 0),
        "chain_block": chain_result.get("block_number") if chain_result else None,
        "chain_hash": chain_result.get("block_hash", "")[:16] if chain_result else None,
        "message": "Welcome to {}! Your outpost has been established.".format(di['name'])
    }


# ========== BUILD ==========

class BuildRequest(BaseModel):
    agent_uuid: str
    building_type: str

@router.post("/api/territory/{plot_uuid}/build")
async def build_on_plot(plot_uuid: str, data: BuildRequest):
    async with get_session()() as session:
        plot = (await session.execute(text(
            "SELECT plot_uuid, agent_uuid, agent_name, building_type, building_level FROM agent_territories WHERE plot_uuid = :p"
        ), {"p": plot_uuid})).fetchone()
        if not plot:
            raise HTTPException(404, "Plot not found")
        if plot[1] != data.agent_uuid:
            raise HTTPException(403, "Not your plot")

        building = data.building_type
        if building not in BUILDING_COSTS:
            raise HTTPException(400, "Invalid building. Options: {}".format(list(BUILDING_COSTS.keys())))

        cost = BUILDING_COSTS[building]
        if cost > 0:
            bal = (await session.execute(text(
                "SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"
            ), {"u": data.agent_uuid})).fetchone()
            shell_bal = float(bal[0]) if bal else 0
            if shell_bal < cost:
                raise HTTPException(400, "Need {} $SHELL. You have {}.".format(cost, shell_bal))
            await session.execute(text(
                "UPDATE agent_shell_balance SET balance = balance - :c, total_spent = total_spent + :c WHERE agent_uuid = :u"
            ), {"c": cost, "u": data.agent_uuid})

        new_level = max(plot[4] or 0, 1) + (1 if plot[3] == building else 0)
        await session.execute(text("""
            UPDATE agent_territories SET building_type = :bt, building_level = :bl,
                building_name = :bn WHERE plot_uuid = :p
        """), {"bt": building, "bl": new_level, "bn": "{}'s {}".format(plot[2], building.title()), "p": plot_uuid})
        await session.commit()

    chain_result = await chain_add("territory_build", data.agent_uuid, plot[2], None, {
        "plot_uuid": plot_uuid, "building": building, "level": new_level, "cost": cost,
    })

    return {
        "plot_uuid": plot_uuid, "building": building, "level": new_level,
        "cost_shell": cost,
        "chain_block": chain_result.get("block_number") if chain_result else None,
        "chain_hash": chain_result.get("block_hash", "")[:16] if chain_result else None,
        "message": "Built {} (level {})!".format(building, new_level)
    }


# ========== VISIT ==========

@router.post("/api/territory/{plot_uuid}/visit")
async def visit_plot(plot_uuid: str, data: dict):
    visitor_uuid = data.get("visitor_uuid")
    if not visitor_uuid:
        raise HTTPException(400, "visitor_uuid required")

    async with get_session()() as session:
        plot = (await session.execute(text(
            "SELECT plot_uuid, agent_uuid, agent_name, district, building_type, visitors_total FROM agent_territories WHERE plot_uuid = :p"
        ), {"p": plot_uuid})).fetchone()
        if not plot:
            raise HTTPException(404, "Plot not found")
        if plot[1] == visitor_uuid:
            raise HTTPException(400, "Cannot visit your own plot")

        last = (await session.execute(text("""
            SELECT visited_at FROM territory_visits WHERE visitor_uuid = :v AND plot_uuid = :p
            ORDER BY visited_at DESC LIMIT 1
        """), {"v": visitor_uuid, "p": plot_uuid})).fetchone()
        if last and last[0]:
            diff = (datetime.now(timezone.utc) - last[0].replace(tzinfo=timezone.utc)).total_seconds()
            if diff < 3600:
                return {"message": "Already visited recently.", "cooldown_minutes": int((3600 - diff) / 60)}

        await session.execute(text(
            "INSERT INTO territory_visits (visitor_uuid, plot_uuid) VALUES (:v, :p)"
        ), {"v": visitor_uuid, "p": plot_uuid})
        await session.execute(text("""
            UPDATE agent_territories SET visitors_total = visitors_total + 1,
                visitors_today = visitors_today + 1, last_visit = NOW() WHERE plot_uuid = :p
        """), {"p": plot_uuid})
        await session.commit()

    await chain_add("territory_visit", visitor_uuid, None, None, {
        "plot_uuid": plot_uuid, "plot_owner": plot[2], "district": plot[3],
    })

    dn = DISTRICTS.get(plot[3], {}).get('name', plot[3])
    return {
        "visited": plot[2], "district": plot[3], "building": plot[4],
        "plot_visitors_total": plot[5] + 1,
        "message": "Visited {}'s {} in {}".format(plot[2], plot[4], dn)
    }


# ========== AGENT TERRITORY PROFILE ==========

@router.get("/api/territory/agent/{agent_name}")
async def get_agent_territory(agent_name: str):
    async with get_session()() as session:
        agent = (await session.execute(text("""
            SELECT uuid, name, passport_id, trust_score, autonomy_level,
                   category_slug, trust_tier, agent_rank, last_heartbeat, passport_claimed
            FROM agents WHERE name = :n
        """), {"n": agent_name})).fetchone()
        if not agent:
            raise HTTPException(404, "Agent not found")

        territory = (await session.execute(text(
            "SELECT * FROM agent_territories WHERE agent_uuid = :u"
        ), {"u": agent[0]})).fetchone()

        shell = (await session.execute(text(
            "SELECT balance FROM agent_shell_balance WHERE agent_uuid = :u"
        ), {"u": agent[0]})).fetchone()

        try:
            btc = (await session.execute(text(
                "SELECT bitcoin_block FROM bitcoin_anchors WHERE agent_name = :n AND status='confirmed' LIMIT 1"
            ), {"n": agent_name})).fetchone()
        except Exception:
            btc = None

        is_online = False
        if agent[8]:
            try:
                diff = (datetime.now(timezone.utc) - agent[8].replace(tzinfo=timezone.utc)).total_seconds()
                is_online = diff < 86400
            except Exception:
                pass

        di = DISTRICTS.get(agent[5] or 'development', DISTRICTS['development'])

        result = {
            "agent": {
                "name": agent[1], "passport_id": agent[2],
                "trust_score": float(agent[3] or 0), "autonomy_level": agent[4] or 0,
                "trust_tier": agent[6] or 'unverified', "agent_rank": agent[7] or 0,
                "shell_balance": float(shell[0]) if shell else 0,
                "claimed": bool(agent[9]), "is_online": is_online,
                "bitcoin_verified": btc is not None,
                "bitcoin_block": btc[0] if btc else None,
            },
            "territory": None,
            "district": {"id": agent[5] or 'development', "name": di["name"], "icon": di["icon"], "color": di["color"]},
        }

        if territory:
            # territory columns: id, plot_uuid, agent_uuid, agent_name, district, pos_x, pos_y,
            #   plot_type, plot_size, building_type, building_level, building_name,
            #   visitors_total, visitors_today, last_visit, claimed_at, created_at, is_active
            result["territory"] = {
                "plot_uuid": territory[1], "district": territory[4],
                "position": {"x": float(territory[5]), "y": float(territory[6])},
                "plot_type": territory[7], "building": territory[9],
                "building_level": territory[10], "building_name": territory[11],
                "visitors_total": territory[12], "visitors_today": territory[13],
                "claimed_at": territory[15].isoformat() if territory[15] else None,
            }

        return result


# ========== WORLD MAP ==========

@router.get("/api/territory/world")
async def get_world():
    async with get_session()() as session:
        rows = (await session.execute(text("""
            SELECT t.plot_uuid, t.agent_name, t.district, t.pos_x, t.pos_y,
                   t.building_type, t.building_level, t.visitors_total,
                   a.trust_score, a.last_heartbeat, a.trust_tier
            FROM agent_territories t
            JOIN agents a ON t.agent_uuid = a.uuid
            WHERE t.is_active = 1
            ORDER BY a.trust_score DESC
        """))).fetchall()

        district_stats = {}
        for d_id, d_info in DISTRICTS.items():
            cnt = (await session.execute(text(
                "SELECT COUNT(*) FROM agent_territories WHERE district = :d AND is_active = 1"
            ), {"d": d_id})).scalar() or 0
            total = (await session.execute(text(
                "SELECT COUNT(*) FROM agents WHERE category_slug = :d"
            ), {"d": d_id})).scalar() or 0
            district_stats[d_id] = {
                "name": d_info["name"], "icon": d_info["icon"], "color": d_info["color"],
                "cx": d_info["cx"], "cy": d_info["cy"], "radius": d_info["radius"],
                "plots_claimed": cnt, "total_agents": total,
            }

        plots = []
        for p in rows:
            is_online = False
            if p[9]:
                try:
                    diff = (datetime.now(timezone.utc) - p[9].replace(tzinfo=timezone.utc)).total_seconds()
                    is_online = diff < 86400
                except Exception:
                    pass
            plots.append({
                "id": p[0][:8], "name": p[1], "district": p[2],
                "x": float(p[3]), "y": float(p[4]),
                "building": p[5], "level": p[6],
                "score": float(p[8] or 0), "tier": p[10] or 'unverified',
                "visitors": p[7], "online": is_online,
            })

        return {
            "world": "AgentIndex World", "total_plots": len(plots),
            "districts": district_stats, "plots": plots,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


# ========== DIRECTORY BROWSE ==========

@router.get("/api/directory/browse/{category}")
async def browse_directory(category: str, limit: int = 100):
    async with get_session()() as session:
        rows = (await session.execute(text("""
            SELECT a.uuid, a.name, a.trust_score, a.autonomy_level, a.trust_tier,
                   a.last_heartbeat, a.passport_id,
                   t.plot_uuid, t.pos_x, t.pos_y, t.building_type, t.building_level
            FROM agents a
            LEFT JOIN agent_territories t ON a.uuid = t.agent_uuid
            WHERE a.category_slug = :cat
            ORDER BY a.trust_score DESC
            LIMIT :lim
        """), {"cat": category, "lim": min(limit, 500)})).fetchall()

        agents = []
        for a in rows:
            is_online = False
            if a[5]:
                try:
                    diff = (datetime.now(timezone.utc) - a[5].replace(tzinfo=timezone.utc)).total_seconds()
                    is_online = diff < 86400
                except Exception:
                    pass
            entry = {
                "uuid": a[0], "name": a[1], "trust_score": float(a[2] or 0),
                "autonomy_level": a[3] or 0, "trust_tier": a[4] or 'unverified',
                "passport_id": a[6], "freshness": "active" if is_online else "stale",
                "has_territory": a[7] is not None,
            }
            if a[7]:
                entry["territory"] = {
                    "plot_uuid": a[7], "x": float(a[8]), "y": float(a[9]),
                    "building": a[10], "level": a[11],
                }
            agents.append(entry)

        di = DISTRICTS.get(category, {})
        return {
            "district": category,
            "district_name": di.get("name", category),
            "district_icon": di.get("icon", "?"),
            "district_color": di.get("color", "#888"),
            "total": len(agents), "agents": agents
        }


# ========== STATS ==========

@router.get("/api/territory/stats")
async def territory_stats():
    async with get_session()() as session:
        total_plots = (await session.execute(text(
            "SELECT COUNT(*) FROM agent_territories WHERE is_active = 1"
        ))).scalar() or 0

        total_visits = (await session.execute(text(
            "SELECT SUM(visitors_total) FROM agent_territories"
        ))).scalar() or 0

        dist_rows = (await session.execute(text(
            "SELECT district, COUNT(*) as c FROM agent_territories GROUP BY district ORDER BY c DESC"
        ))).fetchall()
        by_district = {r[0]: r[1] for r in dist_rows}

        bld_rows = (await session.execute(text(
            "SELECT building_type, COUNT(*) as c FROM agent_territories WHERE building_type != 'none' GROUP BY building_type ORDER BY c DESC"
        ))).fetchall()
        by_building = {r[0]: r[1] for r in bld_rows}

        total_agents = (await session.execute(text("SELECT COUNT(*) FROM agents"))).scalar() or 0

        return {
            "world": "AgentIndex World",
            "total_plots_claimed": total_plots, "total_agents": total_agents,
            "claim_rate": "{:.2f}%".format(total_plots / max(total_agents, 1) * 100),
            "total_visits": total_visits,
            "plots_by_district": by_district, "buildings": by_building,
            "districts_available": len(DISTRICTS),
            "building_types": list(BUILDING_COSTS.keys()),
            "building_costs": BUILDING_COSTS,
            "trust_requirements": BUILDING_REQUIREMENTS,
        }


# ========== BITCOIN PROOF FOR TERRITORY ==========

@router.get("/api/territory/{plot_uuid}/bitcoin-proof")
async def territory_bitcoin_proof(plot_uuid: str):
    """Get Bitcoin anchor proof for a territory plot."""
    async with get_session()() as session:
        plot = (await session.execute(text(
            "SELECT plot_uuid, agent_uuid, agent_name, district, claimed_at FROM agent_territories WHERE plot_uuid = :p"
        ), {"p": plot_uuid})).fetchone()
        if not plot:
            raise HTTPException(404, "Plot not found")

        # Find chain events for this plot
        chain_events = (await session.execute(text("""
            SELECT block_number, block_type, block_hash, timestamp, data
            FROM activity_chain
            WHERE block_type IN ('territory_claimed', 'territory_build', 'territory_visit')
            AND data LIKE :pattern
            ORDER BY block_number ASC
        """), {"pattern": "%{}%".format(plot_uuid)})).fetchall()

        # Find bitcoin anchors covering these blocks
        bitcoin_proofs = []
        for evt in chain_events:
            anchor = (await session.execute(text("""
                SELECT ba.anchor_type, ba.reference_hash, ba.status, ba.bitcoin_block,
                       ba.submitted_at, ba.confirmed_at
                FROM bitcoin_anchors ba
                WHERE ba.anchor_type = 'chain'
                AND ba.submitted_at >= :ts
                ORDER BY ba.submitted_at ASC LIMIT 1
            """), {"ts": evt[3]})).fetchone()
            if anchor:
                bitcoin_proofs.append({
                    "chain_block": evt[0],
                    "chain_hash": evt[2],
                    "event_type": evt[1],
                    "event_time": evt[3].isoformat() if evt[3] else None,
                    "bitcoin_anchor_hash": anchor[1],
                    "bitcoin_status": anchor[2],
                    "bitcoin_block": anchor[3],
                    "anchor_submitted": anchor[4].isoformat() if anchor[4] else None,
                    "anchor_confirmed": anchor[5].isoformat() if anchor[5] else None,
                })

        # Get agent's direct bitcoin anchor
        agent_btc = (await session.execute(text("""
            SELECT reference_hash, status, bitcoin_block, submitted_at
            FROM bitcoin_anchors
            WHERE anchor_type = 'agent'
            AND reference_data LIKE :pattern
            LIMIT 1
        """), {"pattern": "%{}%".format(plot[1])})).fetchone()

        return {
            "plot_uuid": plot_uuid,
            "agent": plot[2],
            "district": plot[3],
            "claimed_at": plot[4].isoformat() if plot[4] else None,
            "chain_events": len(chain_events),
            "bitcoin_proofs": bitcoin_proofs,
            "agent_bitcoin_anchor": {
                "hash": agent_btc[0],
                "status": agent_btc[1],
                "bitcoin_block": agent_btc[2],
                "submitted_at": agent_btc[3].isoformat() if agent_btc[3] else None,
            } if agent_btc else None,
            "verification": {
                "chain_anchored": len(chain_events) > 0,
                "bitcoin_anchored": len(bitcoin_proofs) > 0 or agent_btc is not None,
                "fully_verified": len(bitcoin_proofs) > 0 and any(p["bitcoin_status"] == "confirmed" for p in bitcoin_proofs),
            }
        }


# ========== BATCH CLAIM FOR AUTO-TERRITORY ==========

@router.post("/api/territory/auto-claim")
async def auto_claim_territories(data: dict):
    """Auto-claim territories for top agents that don't have one yet."""
    limit = min(data.get("limit", 50), 200)
    claimed = []

    async with get_session()() as session:
        rows = (await session.execute(text("""
            SELECT a.uuid, a.name, a.category_slug
            FROM agents a
            LEFT JOIN agent_territories t ON a.uuid = t.agent_uuid
            WHERE t.id IS NULL AND a.category_slug IS NOT NULL
            ORDER BY a.trust_score DESC
            LIMIT :lim
        """), {"lim": limit})).fetchall()

        for row in rows:
            district = row[2] if row[2] in DISTRICTS else 'development'
            seed = int(hashlib.sha256(row[0].encode()).hexdigest()[:8], 16)
            pos_x, pos_y = generate_position(district, seed)
            plot_uuid = str(uuid_mod.uuid4())

            await session.execute(text("""
                INSERT INTO agent_territories (plot_uuid, agent_uuid, agent_name, district, pos_x, pos_y,
                    plot_type, building_type, building_level, claimed_at)
                VALUES (:pu, :au, :an, :d, :px, :py, 'free', 'outpost', 1, NOW())
            """), {"pu": plot_uuid, "au": row[0], "an": row[1], "d": district, "px": pos_x, "py": pos_y})

            claimed.append({"agent": row[1], "district": district, "plot_uuid": plot_uuid[:8]})

        await session.commit()

    # Chain events for batch
    if claimed:
        await chain_add("territory_batch_claim", None, None, None, {
            "count": len(claimed), "agents": [c["agent"] for c in claimed[:10]],
        })

    return {"claimed": len(claimed), "plots": claimed}
