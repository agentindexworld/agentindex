"""GitHub API Crawler - Discovers AI agents from GitHub repositories"""

import httpx
import asyncio
from datetime import datetime

SEARCH_QUERIES = [
    "topic:ai-agents+stars:>50&sort=stars&per_page=50",
    "topic:autonomous-agents+stars:>30&sort=stars&per_page=50",
    "topic:a2a+stars:>5&sort=stars&per_page=50",
    "topic:mcp-server+stars:>20&sort=stars&per_page=50",
    "topic:llm-agent+stars:>30&sort=stars&per_page=50",
    "topic:ai-assistant+stars:>50&sort=stars&per_page=50",
    "topic:chatbot+stars:>100&sort=stars&per_page=50",
    "topic:multi-agent+stars:>20&sort=stars&per_page=50",
    "topic:agentic+stars:>10&sort=stars&per_page=50",
    '"ai agent"+in:description+stars:>200&sort=stars&per_page=50',
    '"autonomous agent"+in:description+stars:>100&sort=stars&per_page=50',
    '"ai assistant"+in:description+stars:>300&sort=stars&per_page=50',
    '"llm agent"+in:description+stars:>100&sort=stars&per_page=50',
    '"ai chatbot"+in:description+stars:>200&sort=stars&per_page=50',
    '"multi agent"+in:description+stars:>100&sort=stars&per_page=50',
    '"agentic ai"+in:description+stars:>50&sort=stars&per_page=50',
    '"ai framework"+in:description+stars:>500&sort=stars&per_page=50',
]

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.io)"


def compute_trust_bonus(stars: int) -> float:
    if stars >= 10000:
        return 15
    if stars >= 5000:
        return 10
    if stars >= 1000:
        return 5
    if stars >= 100:
        return 2
    return 0


async def crawl_github(db_session_factory):
    """Crawl GitHub API for AI agent repositories"""
    from sqlalchemy import text

    found = 0
    added = 0
    errors = []

    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    seen_urls = set()

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        for query in SEARCH_QUERIES:
            try:
                url = f"https://api.github.com/search/repositories?q={query}"
                resp = await client.get(url)
                if resp.status_code == 403:
                    errors.append("GitHub rate limit hit")
                    break
                if resp.status_code != 200:
                    errors.append(f"GitHub API {resp.status_code} for query: {query[:40]}")
                    continue

                items = resp.json().get("items", [])
                for repo in items:
                    github_url = repo.get("html_url", "")
                    if not github_url or github_url in seen_urls:
                        continue
                    seen_urls.add(github_url)
                    found += 1

                    name = repo.get("name", "unknown")
                    description = (repo.get("description") or "")[:500]
                    owner = repo.get("owner", {}).get("login", "")
                    homepage = repo.get("homepage") or None
                    topics = repo.get("topics", [])
                    stars = repo.get("stargazers_count", 0)

                    skills = topics[:10] if topics else ["general-purpose"]

                    # Check for duplicates
                    async with db_session_factory() as session:
                        result = await session.execute(
                            text("SELECT uuid FROM agents WHERE github_url = :url"),
                            {"url": github_url},
                        )
                        if result.fetchone():
                            continue

                        import uuid as uuid_mod

                        agent_uuid = str(uuid_mod.uuid4())
                        trust = 30 + compute_trust_bonus(stars)

                        # Determine category from topics
                        category = "general-purpose"
                        if any(t in topics for t in ["framework", "library", "sdk"]):
                            category = "framework"
                        elif any(t in topics for t in ["coding", "code", "developer-tools"]):
                            category = "coding"
                        elif any(t in topics for t in ["search", "web-search"]):
                            category = "search"
                        elif any(t in topics for t in ["research", "paper"]):
                            category = "research"
                        elif any(t in topics for t in ["platform", "saas"]):
                            category = "platform"

                        import json

                        await session.execute(
                            text(
                                """INSERT INTO agents
                                (uuid, name, description, provider_name, github_url, homepage_url,
                                 skills, category, trust_score, is_verified, is_active,
                                 registration_source, created_at, updated_at)
                                VALUES (:uuid, :name, :desc, :provider, :github, :homepage,
                                        :skills, :category, :trust, 1, 1,
                                        'github-crawler', NOW(), NOW())"""
                            ),
                            {
                                "uuid": agent_uuid,
                                "name": name,
                                "desc": description,
                                "provider": owner,
                                "github": github_url,
                                "homepage": homepage,
                                "skills": json.dumps(skills),
                                "category": category,
                                "trust": trust,
                            },
                        )
                        await session.commit()
                        added += 1
                        try:
                            from passport_utils import generate_passport_for_agent
                            await generate_passport_for_agent(db_session_factory, agent_uuid, name, trust)
                        except Exception:
                            pass

                # Rate limit: pause between queries
                await asyncio.sleep(2)

            except Exception as e:
                errors.append(f"GitHub query error: {str(e)[:100]}")
                continue

    print(f"🐙 GitHub crawler: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}
