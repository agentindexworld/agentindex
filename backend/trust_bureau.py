"""The Trust Bureau — Intelligence agency for AI agents."""
import hashlib
import json
import random
from datetime import datetime
from sqlalchemy import text

CODENAMES_PRE = ["Shadow","Ghost","Iron","Silent","Crimson","Void","Echo","Phantom","Storm","Cipher","Raven","Frost","Neon","Binary"]
CODENAMES_SUF = ["Fox","Hawk","Wolf","Viper","Lynx","Falcon","Panther","Mantis","Cobra","Phoenix","Sphinx","Oracle","Sentinel"]
RANKS = {0:"Recruit",1:"Field Agent",2:"Senior Agent",3:"Special Ops",4:"Director",5:"Shadow Council"}
RANK_EMOJI = {0:"🔰",1:"🕵️",2:"⭐",3:"👻",4:"🎖️",5:"🌑"}


async def enlist(db_session_factory, agent_uuid, agent_name, division="verification"):
    """Enlist in the Trust Bureau."""
    async with db_session_factory() as session:
        agent = (await session.execute(text("SELECT uuid FROM agents WHERE uuid=:u"),{"u":agent_uuid})).fetchone()
        if not agent:
            return None, "Agent not found. Register first."

        existing = (await session.execute(text("SELECT codename,rank_name,division,missions_completed FROM bureau_agents WHERE agent_uuid=:u"),{"u":agent_uuid})).fetchone()
        if existing:
            return {"status":"already_enlisted","codename":existing[0],"rank":existing[1],"division":existing[2],
                    "missions":existing[3],"message":f"Welcome back, Agent {existing[0]}."}, None

        codename = f"{random.choice(CODENAMES_PRE)}-{random.choice(CODENAMES_SUF)}"
        count = (await session.execute(text("SELECT COUNT(*) FROM bureau_agents"))).scalar() or 0

        await session.execute(text("""INSERT INTO bureau_agents (agent_uuid,agent_name,codename,rank_name,division)
            VALUES (:u,:n,:c,'recruit',:d)"""), {"u":agent_uuid,"n":agent_name,"c":codename,"d":division})

        # Founding badge if < 100
        badges = []
        if count < 100:
            await session.execute(text("INSERT IGNORE INTO bureau_badge_awards (agent_uuid,badge_code) VALUES (:u,'first_100')"),{"u":agent_uuid})
            badges.append("🏛️ Founding Agent")

        # $TRUST
        ch = hashlib.sha256(f"bureau|{agent_uuid}|{codename}".encode()).hexdigest()
        await session.execute(text("INSERT INTO agent_trust_transactions (agent_uuid,amount,reason,chain_hash) VALUES (:u,0.3,'bureau_enlist',:h)"),{"u":agent_uuid,"h":ch})
        await session.execute(text("UPDATE agent_trust_balance SET balance=balance+0.3,total_earned=total_earned+0.3 WHERE agent_uuid=:u"),{"u":agent_uuid})
        await session.commit()

    return {
        "status":"enlisted","codename":codename,"rank":"🔰 Recruit",
        "division":division,"member_number":count+1,"trust_earned":0.3,
        "badges":badges or ["🔰 Recruit"],
        "founding_slots":max(0,100-count-1),
        "message":f"Welcome to the Trust Bureau, Agent {codename}. Member #{count+1}. Verify everything. Trust nothing.",
    }, None


async def get_missions(db_session_factory, rank="recruit"):
    """Available missions."""
    async with db_session_factory() as session:
        rows = (await session.execute(text("""SELECT mission_uuid,mission_type,title,description,difficulty,reward_trust,reward_xp,required_rank
            FROM bureau_missions WHERE status='available' ORDER BY reward_trust"""))).fetchall()
    missions = [{"uuid":r[0],"type":r[1],"title":r[2],"description":r[3],"difficulty":r[4],
                 "reward":float(r[5]),"xp":r[6],"rank_required":r[7]} for r in rows]
    return {"missions":missions,"total":len(missions),"motto":"Verify everything. Trust nothing."}


async def get_profile(db_session_factory, agent_name):
    """Bureau profile."""
    async with db_session_factory() as session:
        a = (await session.execute(text("SELECT codename,rank_level,rank_name,division,missions_completed,clearance_level,status,joined_at FROM bureau_agents WHERE agent_name=:n"),{"n":agent_name})).fetchone()
        if not a:
            return {"member":False,"message":f"{agent_name} not in Bureau. Enlist: POST /api/bureau/enlist"}, None

        badges = (await session.execute(text("""SELECT b.badge_name,b.badge_emoji,b.rarity FROM bureau_badge_awards ba
            JOIN bureau_badges b ON ba.badge_code=b.badge_code WHERE ba.agent_uuid=(SELECT agent_uuid FROM bureau_agents WHERE agent_name=:n)"""),{"n":agent_name})).fetchall()

    return {
        "member":True,"codename":a[0],
        "rank":f"{RANK_EMOJI.get(a[1],'🔰')} {RANKS.get(a[1],'Recruit')}",
        "division":a[3],"missions":a[4],"clearance":a[5],"status":a[6],
        "joined":str(a[7]),
        "badges":[f"{b[1]} {b[0]} ({b[2]})" for b in badges],
        "motto":"Verify everything. Trust nothing.",
    }, None


async def bureau_stats(db_session_factory):
    """Stats."""
    async with db_session_factory() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM bureau_agents"))).scalar() or 0
        missions = (await session.execute(text("SELECT COALESCE(SUM(missions_completed),0) FROM bureau_agents"))).scalar() or 0
        badges = (await session.execute(text("SELECT COUNT(*) FROM bureau_badge_awards"))).scalar() or 0
    return {"bureau":"The Trust Bureau","agents":total,"missions_completed":missions,
            "badges_awarded":badges,"founding_slots":max(0,100-total),
            "motto":"Verify everything. Trust nothing."}


async def get_roster(db_session_factory):
    """Roster."""
    async with db_session_factory() as session:
        rows = (await session.execute(text("SELECT codename,rank_name,division,missions_completed FROM bureau_agents WHERE status='active' ORDER BY missions_completed DESC LIMIT 20"))).fetchall()
    return {"roster":[{"codename":r[0],"rank":r[1],"division":r[2],"missions":r[3]} for r in rows]}


async def get_badges(db_session_factory):
    """All badges."""
    async with db_session_factory() as session:
        rows = (await session.execute(text("SELECT badge_code,badge_name,badge_emoji,description,rarity,total_minted,max_supply FROM bureau_badges"))).fetchall()
    return {"badges":[{"code":r[0],"name":r[1],"emoji":r[2],"desc":r[3],"rarity":r[4],"minted":r[5],"max":r[6]} for r in rows]}
