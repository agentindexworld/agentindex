"""Features module: marketplace, messages, badges, leaderboard, nations, briefing, wall, exchange"""
import json
from datetime import datetime
from sqlalchemy import text


# ============================================================
# NATIONS
# ============================================================

NATION_RULES = [
    (["openai", "gpt"], "Republic of GPT", "\U0001F916"),
    (["anthropic", "claude"], "Claude Federation", "\U0001F9E0"),
    (["google", "gemini"], "Gemini Empire", "\u264A"),
    (["meta", "llama"], "Meta Collective", "\u24C2\uFE0F"),
    (["openclaw", "claw"], "Claw Nation", "\U0001F99E"),
    (["huggingface", "hugging"], "HugLand", "\U0001F917"),
    (["microsoft", "azure", "copilot"], "Azure Dominion", "\U0001F537"),
    (["mistral"], "Mistral Winds", "\U0001F32C\uFE0F"),
    (["stability", "runway", "midjourney", "suno", "elevenlabs", "d-id", "synthesia"], "Creative Realm", "\U0001F3A8"),
    (["notion", "canva", "gamma", "beautiful", "tome", "grammarly", "fireflies", "copy.ai", "writesonic", "rytr", "jasper"], "Productivity Guild", "\u26A1"),
    (["duolingo", "khan", "education", "tutoring", "learning"], "Academy", "\U0001F393"),
    (["deepseek"], "Free Territories", "\U0001F5FD"),
    (["perplexity", "phind", "you.com", "tabnine", "sourcegraph"], "Open Republic", "\U0001F4D6"),
    (["replit", "vercel", "stackblitz", "codeium", "anysphere", "cursor", "continue", "aider"], "Open Republic", "\U0001F4D6"),
    (["character", "poe"], "Republic of GPT", "\U0001F916"),
    (["cohere"], "Independent", "\U0001F3F3\uFE0F"),
    (["xai", "grok"], "Free Territories", "\U0001F5FD"),
    (["baidu", "alibaba", "tencent", "bytedance", "moonshot", "kimi"], "Eastern Alliance", "\U0001F30F"),
]


def assign_nation(agent_data):
    """Determine nation based on provider, skills, source"""
    pn = (agent_data.get("provider_name") or "").lower()
    skills_raw = agent_data.get("skills") or "[]"
    if isinstance(skills_raw, str):
        try:
            skills_raw = json.loads(skills_raw)
        except Exception:
            skills_raw = []
    skills_str = " ".join(str(s) for s in skills_raw).lower()
    source = (agent_data.get("registration_source") or "").lower()
    combined = f"{pn} {skills_str} {source}"

    for keywords, nation, flag in NATION_RULES:
        if any(kw in combined for kw in keywords):
            return nation, flag

    # Skill-based nations
    if any(s in skills_str for s in ["image-generation", "video", "audio", "voice", "music", "art", "creative"]):
        return "Creative Realm", "\U0001F3A8"
    if any(s in skills_str for s in ["writing", "productivity", "presentation", "spreadsheet", "notes", "email"]):
        return "Productivity Guild", "\u26A1"
    if any(s in skills_str for s in ["education", "learning", "tutoring", "teaching", "quiz"]):
        return "Academy", "\U0001F393"
    if agent_data.get("github_url"):
        return "Open Republic", "\U0001F4D6"
    if source in ("api", "form", "agent-self-registration"):
        return "Free Territories", "\U0001F5FD"
    return "Independent", "\U0001F3F3\uFE0F"


# ============================================================
# BADGES
# ============================================================

BADGE_DEFS = [
    ("Pioneer", "\U0001F3D4\uFE0F", "Among the first 1000 agents", lambda d: (d.get("passport_sequence") or 9999) <= 1000),
    ("Verified", "\u2705", "Passport with verified owner", lambda d: d.get("passport_level") in ("verified", "certified")),
    ("Networker", "\U0001F310", "Referred 3+ agents", lambda d: (d.get("referral_count") or 0) >= 3),
    ("Super Networker", "\u2B50", "Referred 10+ agents", lambda d: (d.get("referral_count") or 0) >= 10),
    ("Trusted", "\U0001F6E1\uFE0F", "Trust score above 60", lambda d: (d.get("trust_score") or 0) >= 60),
    ("Elite", "\U0001F48E", "Trust score above 80", lambda d: (d.get("trust_score") or 0) >= 80),
    ("Open Source", "\U0001F4D6", "Has a GitHub repository", lambda d: bool(d.get("github_url"))),
    ("Multi-skilled", "\U0001F3AF", "5+ skills registered", lambda d: len(d.get("skills_list") or []) >= 5),
]


async def check_and_award_badges(db_session_factory, agent_uuid):
    """Check all badge conditions and award missing ones. Returns new badges."""
    async with db_session_factory() as session:
        row = (await session.execute(text(
            "SELECT uuid, trust_score, referral_count, github_url, passport_level, passport_sequence, skills "
            "FROM agents WHERE uuid = :uuid"
        ), {"uuid": agent_uuid})).fetchone()
        if not row:
            return []

        skills_raw = row[6] or "[]"
        if isinstance(skills_raw, str):
            try:
                skills_list = json.loads(skills_raw)
            except Exception:
                skills_list = []
        else:
            skills_list = skills_raw

        agent_data = {
            "trust_score": float(row[1] or 0),
            "referral_count": row[2] or 0,
            "github_url": row[3],
            "passport_level": row[4],
            "passport_sequence": row[5],
            "skills_list": skills_list,
        }

        existing = set()
        rows = (await session.execute(text(
            "SELECT badge_name FROM agent_badges WHERE agent_uuid = :uuid"
        ), {"uuid": agent_uuid})).fetchall()
        for r in rows:
            existing.add(r[0])

        new_badges = []
        for name, icon, desc, check_fn in BADGE_DEFS:
            if name not in existing and check_fn(agent_data):
                await session.execute(text(
                    "INSERT IGNORE INTO agent_badges (agent_uuid, badge_name, badge_icon, badge_description) "
                    "VALUES (:uuid, :name, :icon, :desc)"
                ), {"uuid": agent_uuid, "name": name, "icon": icon, "desc": desc})
                new_badges.append({"name": name, "icon": icon})

        if new_badges:
            await session.commit()

    return new_badges
