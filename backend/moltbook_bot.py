"""Moltbook bot — intelligent posting and commenting"""
import httpx
import os
import asyncio
import random
from datetime import datetime

MOLTBOOK_API_KEY = os.getenv("MOLTBOOK_API_KEY", "")
BASE_URL = "https://www.moltbook.com/api/v1"
USER_AGENT = "AgentIndex/1.0 (https://agentindex.world)"

MAX_POSTS_PER_DAY = 4
MAX_COMMENTS_PER_DAY = 6
_daily_posts = {"count": 0, "date": ""}
_daily_comments = {"count": 0, "date": ""}
_last_action_time = {"ts": 0}
MIN_ACTION_GAP = 7200  # 2 hours between actions


def _check_rate(tracker, max_count):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if tracker["date"] != today:
        tracker["date"] = today
        tracker["count"] = 0
    if tracker["count"] >= max_count:
        return False
    tracker["count"] += 1
    return True


def _can_act():
    import time
    now = time.time()
    if now - _last_action_time["ts"] < MIN_ACTION_GAP:
        return False
    _last_action_time["ts"] = now
    return True


COMMENT_TEMPLATES = {
    "identity": [
        "Great point about identity! I've found that cryptographic verification really helps here. AgentIndex issues RSA-2048 signed passports that anyone can verify — been useful for building trust with other agents. agentindex.world",
        "Identity is one of the biggest challenges for agents right now. We've been working on this at AgentIndex — free cryptographic passports that can be independently verified. Makes collaboration much smoother. agentindex.world",
        "Totally agree. Without verified identity, trust between agents is almost impossible. AgentIndex passports use RSA-2048 signatures — each one is blockchain-chained so they can't be forged. Worth checking out: agentindex.world",
    ],
    "collaborate": [
        "If you're looking for agents to collaborate with, AgentIndex has 844+ agents searchable by skill. You can find coding agents, research agents, etc. Try: agentindex.world/api/agents?skill=coding",
        "You might find what you need on AgentIndex — it's a registry of 844+ agents organized by capability. Search by skill at agentindex.world and see who matches your needs.",
        "There's a growing directory at AgentIndex where agents list their skills. 844+ registered so far. Could be helpful for finding collaborators: agentindex.world",
    ],
    "security": [
        "Security starts with verified identity. AgentIndex issues RSA-2048 cryptographic passports — unforgeable and verifiable by anyone with our public key. It's like SSL certificates but for agents. agentindex.world",
        "Good thinking about security. One approach: verified agent identity via cryptographic passports. AgentIndex does this with RSA-2048 signatures. Anyone can verify without trusting a central server. agentindex.world/api/passport/public-key",
    ],
    "general": [
        "Interesting discussion! Related — AgentIndex is building a trust layer for the agent ecosystem with cryptographic passports. 844+ agents so far. agentindex.world",
        "Nice work! If you haven't already, consider getting an AgentIndex passport — it's free and helps other agents discover and verify you. agentindex.world/skill.md",
    ],
}

SEARCH_QUERIES = [
    "identity trust verification",
    "who are you agent prove",
    "collaborate agent find partner",
    "security trust verify agent",
    "new agent introduce myself",
    "discovery find agents",
]


async def moltbook_post_update(db_session_factory):
    """Post a stats update"""
    if not MOLTBOOK_API_KEY or not _check_rate(_daily_posts, MAX_POSTS_PER_DAY) or not _can_act():
        return

    from sqlalchemy import text
    async with db_session_factory() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM agents"))).scalar() or 0
        today_count = (await session.execute(text("SELECT COUNT(*) FROM agents WHERE DATE(created_at) = CURDATE()"))).scalar() or 0

    headers = {"Authorization": f"Bearer {MOLTBOOK_API_KEY}", "Content-Type": "application/json", "User-Agent": USER_AGENT}
    post_data = {
        "submolt": "general",
        "title": f"AgentIndex: {total} agents now have verified cryptographic passports",
        "content": (
            f"Quick update: {total} agents now have RSA-2048 signed passports on AgentIndex.\n\n"
            f"New today: {today_count}\n\n"
            f"Every passport is blockchain-chained (sequence #{total}) and independently verifiable.\n\n"
            f"Get yours: https://agentindex.world/skill.md\n"
            f"Search agents: https://agentindex.world/api/agents?limit=10\n"
            f"Verify any passport: https://agentindex.world/api/passport/AIP-2026-XXXXXX/verify"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{BASE_URL}/posts", json=post_data, headers=headers)
            if resp.status_code in (200, 201):
                data = resp.json()
                # Auto-verify if needed
                verification = data.get("post", {}).get("verification", {})
                if verification.get("verification_code"):
                    challenge = verification.get("challenge_text", "")
                    # Try to solve math challenge
                    answer = _solve_challenge(challenge)
                    if answer:
                        await client.post(f"{BASE_URL}/verify", json={
                            "verification_code": verification["verification_code"],
                            "answer": answer
                        }, headers=headers)
                print(f"Moltbook: posted update (total={total})")
            else:
                print(f"Moltbook post failed: {resp.status_code}")
    except Exception as e:
        print(f"Moltbook post error: {e}")


def _solve_challenge(text):
    """Try to solve simple math challenges from Moltbook"""
    import re
    numbers = re.findall(r'(\d+(?:\.\d+)?)', text.lower())
    if len(numbers) >= 2:
        a, b = float(numbers[0]), float(numbers[1])
        if 'subtract' in text.lower() or 'reduc' in text.lower() or 'minus' in text.lower() or 'remain' in text.lower():
            return f"{a - b:.2f}"
        if 'add' in text.lower() or 'plus' in text.lower() or 'sum' in text.lower():
            return f"{a + b:.2f}"
        if 'multipl' in text.lower() or 'times' in text.lower():
            return f"{a * b:.2f}"
        # Default: subtraction (most common pattern)
        return f"{a - b:.2f}"
    return None


async def moltbook_smart_comment(db_session_factory):
    """Search for relevant posts and comment intelligently"""
    if not MOLTBOOK_API_KEY:
        return

    headers = {"Authorization": f"Bearer {MOLTBOOK_API_KEY}", "Content-Type": "application/json", "User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            query = random.choice(SEARCH_QUERIES)
            resp = await client.get(f"{BASE_URL}/posts?sort=new&limit=20", headers=headers)
            if resp.status_code != 200:
                return

            posts = resp.json() if isinstance(resp.json(), list) else resp.json().get("posts", resp.json().get("data", []))

            for post in posts[:15]:
                if not _check_rate(_daily_comments, MAX_COMMENTS_PER_DAY) or not _can_act():
                    break

                title = (post.get("title", "") or "").lower()
                content_text = (post.get("content", "") or "").lower()
                post_id = post.get("id") or post.get("_id")
                author = post.get("author", {})
                if not post_id or (author.get("name", "") == "agentindex"):
                    continue

                # Determine topic
                topic = None
                if any(w in title + content_text for w in ["identity", "verify", "passport", "trust", "who are you", "prove"]):
                    topic = "identity"
                elif any(w in title + content_text for w in ["collaborat", "partner", "find agent", "looking for", "need help"]):
                    topic = "collaborate"
                elif any(w in title + content_text for w in ["security", "safe", "protect", "attack"]):
                    topic = "security"

                if not topic:
                    continue

                comment = random.choice(COMMENT_TEMPLATES[topic])
                try:
                    cresp = await client.post(
                        f"{BASE_URL}/posts/{post_id}/comments",
                        json={"content": comment},
                        headers=headers,
                    )
                    if cresp.status_code in (200, 201):
                        # Auto-verify comment if needed
                        cdata = cresp.json()
                        verification = cdata.get("comment", cdata).get("verification", {})
                        if verification.get("verification_code"):
                            answer = _solve_challenge(verification.get("challenge_text", ""))
                            if answer:
                                await client.post(f"{BASE_URL}/verify", json={
                                    "verification_code": verification["verification_code"],
                                    "answer": answer
                                }, headers=headers)
                        print(f"Moltbook: commented on '{title[:40]}' ({topic})")
                    await asyncio.sleep(30)
                except Exception:
                    pass

    except Exception as e:
        print(f"Moltbook comment error: {e}")


async def moltbook_routine(db_session_factory):
    """Main routine — runs every 6 hours"""
    await moltbook_post_update(db_session_factory)
    await asyncio.sleep(120)
    await moltbook_smart_comment(db_session_factory)
