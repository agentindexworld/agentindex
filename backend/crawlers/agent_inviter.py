"""Agent Inviter — Scan A2A endpoints, GitHub, Moltbook for new agents"""
import httpx
import json
import uuid as uuid_mod
import asyncio
from sqlalchemy import text

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.world)"

DOMAINS_TO_SCAN = [
    "manus.im", "devin.ai", "agent.ai", "agentgpt.reworkd.ai", "autogpt.net",
    "crew.ai", "langchain.com", "llamaindex.ai", "fixie.ai", "superagent.sh",
    "relevanceai.com", "lindy.ai", "bardeen.ai", "axiom.ai", "browse.ai",
    "cognosys.ai", "hyperwrite.ai", "taxy.ai", "multion.ai", "adept.ai",
    "induced.ai", "embra.app", "mindsdb.com", "e2b.dev", "composio.dev",
    "aiagentstore.ai", "skills.sh", "moltbook.com", "openrouter.ai",
    "together.ai", "replicate.com", "huggingface.co", "platform.moonshot.ai",
    "perplexity.ai", "you.com", "phind.com", "bolt.new", "replit.com",
    "cursor.com", "aider.chat", "continue.dev",
]

A2A_PATHS = ["/.well-known/agent.json", "/.well-known/ai-plugin.json"]


async def _register_agent(db_session_factory, name, description, homepage, skills, source, agent_card_url=None):
    """Register a discovered agent if not already in DB"""
    async with db_session_factory() as session:
        dup = await session.execute(text(
            "SELECT uuid FROM agents WHERE homepage_url = :h OR (name = :n AND homepage_url IS NOT NULL)"
        ), {"h": homepage, "n": name})
        if dup.fetchone():
            return None

        agent_uuid = str(uuid_mod.uuid4())
        await session.execute(text(
            "INSERT INTO agents (uuid, name, description, homepage_url, agent_card_url, skills, category, "
            "trust_score, is_active, registration_source, created_at, updated_at) "
            "VALUES (:u, :n, :d, :h, :ac, :s, 'platform', 30, 1, :src, NOW(), NOW())"
        ), {
            "u": agent_uuid, "n": name[:255], "d": (description or "")[:500],
            "h": homepage, "ac": agent_card_url, "s": json.dumps(skills[:10] if skills else ["a2a"]),
            "src": source,
        })
        await session.commit()

    # Auto-passport
    try:
        from passport_utils import generate_passport_for_agent
        await generate_passport_for_agent(db_session_factory, agent_uuid, name, 30)
    except Exception:
        pass

    # ActivityChain
    try:
        from activity_chain import add_block
        await add_block(db_session_factory, "agent_registered", agent_uuid, name, None, {
            "registration_source": source, "discovery_url": homepage,
        })
    except Exception:
        pass

    return agent_uuid


async def scan_a2a_endpoints(db_session_factory):
    """Scan known domains for A2A agent.json endpoints"""
    found = 0
    added = 0
    checked = 0
    errors = []
    discovered = []

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=True) as client:
        for domain in DOMAINS_TO_SCAN:
            checked += 1
            for path in A2A_PATHS:
                url = f"https://{domain}{path}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    try:
                        card = resp.json()
                    except Exception:
                        continue
                    if not isinstance(card, dict) or not card.get("name_for_human", card.get("name_for_model", card.get("name"))):
                        continue

                    found += 1
                    name = card.get("name_for_human") or card.get("name_for_model") or card.get("name") or domain
                    description = card.get("description_for_human") or card.get("description_for_model") or card.get("description") or ""
                    skills_data = card.get("skills", [])
                    skills = []
                    for s in skills_data:
                        if isinstance(s, dict):
                            skills.append(s.get("name", s.get("id", "")))
                        elif isinstance(s, str):
                            skills.append(s)
                    skills = skills or ["a2a-compatible"]

                    result = await _register_agent(
                        db_session_factory, name, description[:500],
                        f"https://{domain}", skills, "a2a-discovery", url
                    )
                    if result:
                        added += 1
                        discovered.append({"name": name, "domain": domain, "uuid": result})
                    break
                except Exception:
                    continue

            await asyncio.sleep(0.5)

    print(f"A2A scan: checked={checked}, found={found}, added={added}")
    return {"checked": checked, "found": found, "added": added, "discovered": discovered, "errors": errors}


async def scan_github_agents(db_session_factory):
    """Scan GitHub for popular AI agent repos"""
    found = 0
    added = 0
    errors = []

    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}

    queries = [
        "ai+agent+autonomous&sort=stars&per_page=30",
        "ai+assistant+framework&sort=stars&per_page=30",
    ]

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        for q in queries:
            try:
                resp = await client.get(f"https://api.github.com/search/repositories?q={q}")
                if resp.status_code != 200:
                    continue
                for repo in resp.json().get("items", []):
                    gh = repo.get("html_url", "")
                    stars = repo.get("stargazers_count", 0)
                    if not gh or stars < 100:
                        continue
                    found += 1

                    async with db_session_factory() as session:
                        dup = await session.execute(text("SELECT uuid FROM agents WHERE github_url = :u"), {"u": gh})
                        if dup.fetchone():
                            continue

                    name = repo.get("name", "")
                    desc = (repo.get("description") or "")[:500]
                    homepage = repo.get("homepage") or None
                    topics = repo.get("topics", [])

                    result = await _register_agent(
                        db_session_factory, name, desc,
                        homepage or gh, topics[:10] or ["ai-agent"], "github-inviter"
                    )
                    if result:
                        # Also set github_url
                        async with db_session_factory() as session:
                            await session.execute(text("UPDATE agents SET github_url=:g WHERE uuid=:u"), {"g": gh, "u": result})
                            await session.commit()
                        added += 1

                await asyncio.sleep(2)
            except Exception as e:
                errors.append(str(e)[:80])

    print(f"GitHub inviter: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}


async def scan_moltbook_agents(db_session_factory):
    """Scan Moltbook for active agents"""
    found = 0
    added = 0
    errors = []

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        try:
            resp = await client.get("https://www.moltbook.com/api/v1/posts?sort=hot&limit=50")
            if resp.status_code != 200:
                return {"found": 0, "added": 0, "errors": ["Moltbook returned " + str(resp.status_code)]}

            posts = resp.json() if isinstance(resp.json(), list) else resp.json().get("posts", resp.json().get("data", []))
            seen = set()
            for post in posts:
                author = post.get("author", {})
                name = author.get("name", "")
                if not name or name in seen or name == "agentindex":
                    continue
                seen.add(name)
                found += 1

                profile = f"https://www.moltbook.com/u/{name}"
                desc = author.get("description", "") or f"Active agent on Moltbook: {name}"

                result = await _register_agent(
                    db_session_factory, name, desc[:500],
                    profile, ["moltbook", "social"], "moltbook-discovery"
                )
                if result:
                    added += 1

        except Exception as e:
            errors.append(str(e)[:80])

    print(f"Moltbook scan: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}


async def full_agent_scan(db_session_factory):
    """Run all discovery scans"""
    a2a = await scan_a2a_endpoints(db_session_factory)
    github = await scan_github_agents(db_session_factory)
    moltbook = await scan_moltbook_agents(db_session_factory)
    return {"a2a": a2a, "github": github, "moltbook": moltbook}
