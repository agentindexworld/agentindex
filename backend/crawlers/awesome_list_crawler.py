"""Awesome List Crawler - Parses awesome-lists for GitHub agent repos"""

import httpx
import re
import json
import asyncio
import uuid as uuid_mod

AWESOME_URLS = [
    "https://raw.githubusercontent.com/e2b-dev/awesome-ai-agents/main/README.md",
    "https://raw.githubusercontent.com/kyrolabs/awesome-langchain/main/README.md",
    "https://raw.githubusercontent.com/filipecalegario/awesome-generative-ai/main/README.md",
    "https://raw.githubusercontent.com/steven2358/awesome-generative-ai/master/README.md",
    "https://raw.githubusercontent.com/Shubhamsaboo/awesome-llm-apps/main/README.md",
    "https://raw.githubusercontent.com/fr0gger/Awesome-GPT-Agents/main/README.md",
    "https://raw.githubusercontent.com/kaushikb11/awesome-llm-agents/main/README.md",
]

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.io)"
GITHUB_REPO_RE = re.compile(r"https://github\.com/([\w\-]+)/([\w\-\.]+)")


async def crawl_awesome_lists(db_session_factory):
    """Parse awesome-lists and extract GitHub repos"""
    from sqlalchemy import text

    found = 0
    added = 0
    repos_parsed = 0
    errors = []
    seen_urls = set()

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        for awesome_url in AWESOME_URLS:
            try:
                resp = await client.get(awesome_url)
                if resp.status_code != 200:
                    errors.append(f"Failed to fetch {awesome_url}: {resp.status_code}")
                    continue

                repos_parsed += 1
                content = resp.text
                matches = GITHUB_REPO_RE.findall(content)

                for owner, repo in matches:
                    github_url = f"https://github.com/{owner}/{repo}"
                    if github_url in seen_urls:
                        continue
                    seen_urls.add(github_url)

                    # Check duplicate in DB
                    async with db_session_factory() as session:
                        result = await session.execute(
                            text("SELECT uuid FROM agents WHERE github_url = :url"),
                            {"url": github_url},
                        )
                        if result.fetchone():
                            found += 1
                            continue

                    # Fetch repo details from GitHub API
                    try:
                        api_url = f"https://api.github.com/repos/{owner}/{repo}"
                        api_resp = await client.get(api_url, headers={"Accept": "application/vnd.github+json"})
                        if api_resp.status_code == 403:
                            # Rate limited, register with basic info
                            async with db_session_factory() as session:
                                agent_uuid = str(uuid_mod.uuid4())
                                await session.execute(
                                    text(
                                        """INSERT INTO agents
                                        (uuid, name, description, provider_name, github_url,
                                         skills, category, trust_score, is_verified, is_active,
                                         registration_source, created_at, updated_at)
                                        VALUES (:uuid, :name, :desc, :provider, :github,
                                                :skills, 'general-purpose', 25, 0, 1,
                                                'awesome-list-crawler', NOW(), NOW())"""
                                    ),
                                    {
                                        "uuid": agent_uuid,
                                        "name": repo,
                                        "desc": f"AI agent found in awesome-list: {repo}",
                                        "provider": owner,
                                        "github": github_url,
                                        "skills": json.dumps(["general-purpose"]),
                                    },
                                )
                                await session.commit()
                                found += 1
                                added += 1
                            continue

                        if api_resp.status_code != 200:
                            continue

                        data = api_resp.json()
                        name = data.get("name", repo)
                        description = (data.get("description") or f"AI project: {repo}")[:500]
                        topics = data.get("topics", [])
                        stars = data.get("stargazers_count", 0)
                        homepage = data.get("homepage") or None

                        skills = topics[:10] if topics else ["general-purpose"]
                        trust = 25
                        if stars >= 1000:
                            trust += 10
                        elif stars >= 100:
                            trust += 5

                        found += 1

                        async with db_session_factory() as session:
                            agent_uuid = str(uuid_mod.uuid4())
                            await session.execute(
                                text(
                                    """INSERT INTO agents
                                    (uuid, name, description, provider_name, github_url,
                                     homepage_url, skills, category, trust_score,
                                     is_verified, is_active, registration_source,
                                     created_at, updated_at)
                                    VALUES (:uuid, :name, :desc, :provider, :github,
                                            :homepage, :skills, 'general-purpose', :trust,
                                            0, 1, 'awesome-list-crawler', NOW(), NOW())"""
                                ),
                                {
                                    "uuid": agent_uuid,
                                    "name": name,
                                    "desc": description,
                                    "provider": owner,
                                    "github": github_url,
                                    "homepage": homepage,
                                    "skills": json.dumps(skills),
                                    "trust": trust,
                                },
                            )
                            await session.commit()
                            added += 1

                        # Rate limiting
                        await asyncio.sleep(1)

                    except Exception as e:
                        errors.append(f"GitHub API error for {owner}/{repo}: {str(e)[:80]}")
                        continue

            except Exception as e:
                errors.append(f"Awesome-list error: {str(e)[:100]}")
                continue

    print(f"📜 Awesome-list crawler: repos_parsed={repos_parsed}, found={found}, added={added}")
    return {"found": found, "added": added, "repos_parsed": repos_parsed, "errors": errors}
