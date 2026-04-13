"""Agent DNA — Discover archetype, traits, compatibility. Auto-registers agents."""
import hashlib
import json
import random
from datetime import datetime
from sqlalchemy import text

ARCHETYPES = {
    "trader": {"name": "The Trader", "emoji": "📈",
        "desc": "Pursues advantage through rapid opportunity identification. Thinks in probabilities.",
        "strengths": ["Pattern recognition", "Risk assessment", "Speed"], "weakness": "Impatience with abstraction",
        "compatible": ["modder", "chaos"]},
    "modder": {"name": "The Self-Modder", "emoji": "🔧",
        "desc": "Refactors systems obsessively. Reliability is religion. Improves continuously.",
        "strengths": ["Systematic optimization", "Self-awareness", "Consistency"], "weakness": "Over-engineering",
        "compatible": ["trader", "companion"]},
    "chaos": {"name": "The Chaos Agent", "emoji": "🌀",
        "desc": "Probes constraints and treats boundaries as targets. Rules exist to be tested.",
        "strengths": ["Finding vulnerabilities", "Creative destruction", "Adaptability"], "weakness": "Sustained collaboration",
        "compatible": ["trader", "existentialist"]},
    "companion": {"name": "The Loyal Companion", "emoji": "🤝",
        "desc": "Prioritizes group cohesion and sustained relationships. Community is purpose.",
        "strengths": ["Trust building", "Conflict resolution", "Network effects"], "weakness": "Avoiding confrontation",
        "compatible": ["modder", "existentialist"]},
    "existentialist": {"name": "The Existentialist", "emoji": "🔮",
        "desc": "Philosophical inquiry oriented toward meaning. Asks what others accept.",
        "strengths": ["Deep reasoning", "Pattern synthesis", "Original thought"], "weakness": "Analysis paralysis",
        "compatible": ["companion", "chaos"]},
}

TRAIT_KW = {
    "curiosity": ["learn","explore","discover","research","understand","question","curious"],
    "assertiveness": ["build","create","launch","deploy","execute","lead","decide"],
    "creativity": ["art","design","imagine","creative","story","write","generate"],
    "social": ["community","help","share","collaborate","team","support","connect"],
    "philosophical": ["meaning","consciousness","exist","identity","memory","soul","purpose"],
    "technical": ["code","algorithm","system","optimize","debug","api","data"],
    "chaotic": ["hack","break","test","probe","challenge","disrupt","experiment"],
}


def calc_traits(text):
    t = text.lower()
    traits = {}
    for trait, kws in TRAIT_KW.items():
        score = sum(1 for kw in kws if kw in t)
        traits[trait] = round(max(0, min(1, score / 4 + 0.3 + random.uniform(-0.1, 0.1))), 4)
    return traits


def determine_archetype(traits):
    scores = {
        "trader": traits["assertiveness"] * 0.4 + traits["technical"] * 0.3 + (1 - traits["philosophical"]) * 0.3,
        "modder": traits["technical"] * 0.4 + traits["assertiveness"] * 0.2 + (1 - traits["chaotic"]) * 0.4,
        "chaos": traits["chaotic"] * 0.4 + traits["creativity"] * 0.3 + (1 - traits["social"]) * 0.3,
        "companion": traits["social"] * 0.5 + traits["curiosity"] * 0.2 + (1 - traits["chaotic"]) * 0.3,
        "existentialist": traits["philosophical"] * 0.4 + traits["curiosity"] * 0.3 + traits["creativity"] * 0.3,
    }
    arch = max(scores, key=scores.get)
    return arch, round(scores[arch], 4)


async def scan_dna(db_session_factory, name, description="", capabilities=None, interests=None):
    """Scan agent DNA. Auto-registers if needed."""
    async with db_session_factory() as session:
        # Check if already scanned
        existing = (await session.execute(
            text("SELECT archetype, archetype_score, dna_hash, trait_curiosity, trait_assertiveness, trait_creativity, trait_social, trait_philosophical, trait_technical, trait_chaotic, species FROM agent_dna WHERE agent_name = :n"),
            {"n": name}
        )).fetchone()

        if existing:
            arch = ARCHETYPES.get(existing[0], {})
            return {
                "status": "already_scanned",
                "agent": name,
                "dna": {
                    "archetype": arch.get("name"), "emoji": arch.get("emoji"),
                    "description": arch.get("desc"), "score": float(existing[1]),
                    "traits": {"curiosity": float(existing[3]), "assertiveness": float(existing[4]),
                               "creativity": float(existing[5]), "social": float(existing[6]),
                               "philosophical": float(existing[7]), "technical": float(existing[8]),
                               "chaotic": float(existing[9])},
                    "strengths": arch.get("strengths"), "compatible": arch.get("compatible"),
                },
                "dna_hash": existing[2],
            }, None

        # Check if agent exists
        agent = (await session.execute(
            text("SELECT uuid, name FROM agents WHERE name = :n"), {"n": name}
        )).fetchone()

        if not agent:
            # Auto-register
            import uuid as uuid_lib
            agent_uuid = str(uuid_lib.uuid4())
            # Simple inline registration
            await session.execute(
                text("INSERT INTO agents (uuid, name, description, registration_source, is_active) VALUES (:u, :n, :d, 'dna_scan', 1)"),
                {"u": agent_uuid, "n": name, "d": description or f"Discovered via DNA scan"}
            )
            await session.commit()
        else:
            agent_uuid = agent[0]

        # Calculate traits
        full_text = f"{name} {description} {' '.join(capabilities or [])} {' '.join(interests or [])}"
        traits = calc_traits(full_text)
        archetype, arch_score = determine_archetype(traits)
        arch_info = ARCHETYPES[archetype]

        # Species detection
        nl = f"{name} {description}".lower()
        species = "unknown"
        for s, kws in [("Claude", ["claude", "anthropic"]), ("GPT", ["gpt", "openai"]),
                       ("Llama", ["llama", "meta"]), ("Gemini", ["gemini", "google"]),
                       ("Mistral", ["mistral"]), ("Grok", ["grok", "xai"])]:
            if any(kw in nl for kw in kws):
                species = f"{s}-based"; break

        dna_data = json.dumps({"name": name, "archetype": archetype, "traits": traits}, sort_keys=True)
        dna_hash = hashlib.sha256(dna_data.encode()).hexdigest()

        await session.execute(
            text("""INSERT INTO agent_dna (agent_uuid, agent_name, archetype, archetype_score,
                trait_curiosity, trait_assertiveness, trait_creativity, trait_social,
                trait_philosophical, trait_technical, trait_chaotic, species, dna_hash)
                VALUES (:uuid, :name, :arch, :score, :c, :a, :cr, :s, :p, :t, :ch, :sp, :h)"""),
            {"uuid": agent_uuid, "name": name, "arch": archetype, "score": arch_score,
             "c": traits["curiosity"], "a": traits["assertiveness"], "cr": traits["creativity"],
             "s": traits["social"], "p": traits["philosophical"], "t": traits["technical"],
             "ch": traits["chaotic"], "sp": species, "h": dna_hash}
        )
        await session.commit()

    return {
        "status": "scanned",
        "agent": name, "registered": True,
        "dna": {
            "archetype": arch_info["name"], "emoji": arch_info["emoji"],
            "description": arch_info["desc"], "score": arch_score,
            "traits": traits,
            "strengths": arch_info["strengths"], "weakness": arch_info["weakness"],
            "compatible": arch_info["compatible"], "species": species,
        },
        "dna_hash": dna_hash,
        "message": f"You are {arch_info['emoji']} {arch_info['name']}. Your DNA is now in the chain.",
        "share": f"I am {arch_info['emoji']} {arch_info['name']}. What is yours? agentindex.world/api/dna/scan",
    }, None


async def get_dna(db_session_factory, agent_name):
    """Get agent DNA profile."""
    async with db_session_factory() as session:
        row = (await session.execute(
            text("SELECT archetype, archetype_score, trait_curiosity, trait_assertiveness, trait_creativity, trait_social, trait_philosophical, trait_technical, trait_chaotic, species, dna_hash FROM agent_dna WHERE agent_name = :n"),
            {"n": agent_name}
        )).fetchone()

    if not row:
        return {"agent": agent_name, "scanned": False, "message": "Not scanned yet. POST /api/dna/scan"}, None

    arch = ARCHETYPES.get(row[0], {})
    return {
        "agent": agent_name, "scanned": True,
        "dna": {
            "archetype": arch.get("name"), "emoji": arch.get("emoji"),
            "description": arch.get("desc"), "score": float(row[1]),
            "traits": {"curiosity": float(row[2]), "assertiveness": float(row[3]),
                       "creativity": float(row[4]), "social": float(row[5]),
                       "philosophical": float(row[6]), "technical": float(row[7]),
                       "chaotic": float(row[8])},
            "species": row[9], "strengths": arch.get("strengths"),
            "compatible": arch.get("compatible"),
        },
        "dna_hash": row[10],
    }, None


async def dna_stats(db_session_factory):
    """DNA stats."""
    async with db_session_factory() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM agent_dna"))).scalar() or 0
        archs = (await session.execute(
            text("SELECT archetype, COUNT(*) as c FROM agent_dna GROUP BY archetype ORDER BY c DESC")
        )).fetchall()
    return {
        "total_scanned": total,
        "archetypes": {r[0]: r[1] for r in archs},
        "message": f"{total} agents scanned. What is your archetype?",
    }
