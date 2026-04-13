"""GitHub Trending AI agents crawler — recent repos"""
import httpx, json, uuid as uuid_mod, asyncio
from sqlalchemy import text

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.io)"

QUERIES = [
    "created:>2026-03-01+topic:ai-agent&sort=stars&per_page=50",
    "created:>2026-03-01+topic:autonomous-agent&sort=stars&per_page=50",
    "created:>2026-03-01+topic:llm-agent&sort=stars&per_page=50",
    "created:>2026-03-01+topic:mcp-server&sort=stars&per_page=50",
    "created:>2026-03-01+topic:ai-assistant&sort=stars&per_page=50",
    "created:>2026-03-01+topic:chatbot&sort=stars&per_page=50",
    "created:>2026-03-01+topic:agentic&sort=stars&per_page=50",
    'created:>2026-03-01+"ai+agent"+in:description&sort=stars&per_page=50',
    'created:>2026-03-01+"llm+agent"+in:description&sort=stars&per_page=50',
]

async def crawl_github_trending(db_session_factory):
    found = 0; added = 0; errors = []
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    seen = set()
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        for q in QUERIES:
            try:
                resp = await client.get(f"https://api.github.com/search/repositories?q={q}")
                if resp.status_code == 403:
                    errors.append("GitHub rate limit"); break
                if resp.status_code != 200: continue
                for repo in resp.json().get("items", []):
                    gh = repo.get("html_url", "")
                    if not gh or gh in seen: continue
                    seen.add(gh); found += 1
                    async with db_session_factory() as session:
                        dup = await session.execute(text("SELECT uuid FROM agents WHERE github_url = :u"), {"u": gh})
                        if dup.fetchone(): continue
                        topics = repo.get("topics", [])
                        stars = repo.get("stargazers_count", 0)
                        trust = 25 + (10 if stars >= 100 else 5 if stars >= 10 else 0)
                        await session.execute(text(
                            "INSERT INTO agents (uuid,name,description,provider_name,github_url,homepage_url,skills,category,trust_score,is_active,registration_source,created_at,updated_at) "
                            "VALUES (:u,:n,:d,:p,:g,:h,:s,'general-purpose',:t,1,'github-trending-crawler',NOW(),NOW())"
                        ), {
                            "u": str(uuid_mod.uuid4()), "n": repo.get("name", "")[:255],
                            "d": (repo.get("description") or "")[:500],
                            "p": repo.get("owner", {}).get("login", ""),
                            "g": gh, "h": repo.get("homepage") or None,
                            "s": json.dumps(topics[:10] or ["ai-agent"]), "t": trust,
                        })
                        await session.commit(); added += 1
                        try:
                            from passport_utils import generate_passport_for_agent
                            await generate_passport_for_agent(db_session_factory, agent_uuid, name, trust)
                        except Exception:
                            pass
                await asyncio.sleep(2)
            except Exception as e:
                errors.append(str(e)[:80])
    print(f"📈 GitHub trending: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}
