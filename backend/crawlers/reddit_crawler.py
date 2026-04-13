"""Reddit AI agent subreddits crawler"""
import httpx, json, uuid as uuid_mod, re, asyncio
from sqlalchemy import text

USER_AGENT = "AgentIndex/1.0 (AI Agent Registry; contact@agentindex.io)"

SUBREDDITS = ["AI_Agents", "AutoGPT", "LocalLLaMA", "ChatGPT"]
GITHUB_RE = re.compile(r'https://github\.com/([\w\-]+)/([\w\-\.]+)')

async def crawl_reddit(db_session_factory):
    found = 0; added = 0; errors = []
    headers = {"User-Agent": USER_AGENT}
    seen_urls = set()
    async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=True) as client:
        for sub in SUBREDDITS:
            try:
                resp = await client.get(f"https://old.reddit.com/r/{sub}/hot.json?limit=50")
                if resp.status_code != 200:
                    errors.append(f"r/{sub} returned {resp.status_code}")
                    continue
                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                for post in posts:
                    pd = post.get("data", {})
                    body = (pd.get("selftext", "") + " " + (pd.get("url", "") or ""))
                    # Extract GitHub links
                    matches = GITHUB_RE.findall(body)
                    for owner, repo in matches:
                        gh = f"https://github.com/{owner}/{repo}"
                        if gh in seen_urls: continue
                        seen_urls.add(gh); found += 1
                        async with db_session_factory() as session:
                            dup = await session.execute(text("SELECT uuid FROM agents WHERE github_url = :u"), {"u": gh})
                            if dup.fetchone(): continue
                            await session.execute(text(
                                "INSERT INTO agents (uuid,name,description,provider_name,github_url,skills,category,trust_score,is_active,registration_source,created_at,updated_at) "
                                "VALUES (:u,:n,:d,:p,:g,:s,'general-purpose',20,1,'reddit-crawler',NOW(),NOW())"
                            ), {
                                "u": str(uuid_mod.uuid4()), "n": repo[:255],
                                "d": f"AI agent found on r/{sub}: {pd.get('title', '')[:200]}",
                                "p": owner, "g": gh,
                                "s": json.dumps(["ai-agent", "community-discovered"]),
                            })
                            await session.commit(); added += 1
                await asyncio.sleep(2)
            except Exception as e:
                errors.append(f"r/{sub}: {str(e)[:80]}")
    print(f"📱 Reddit crawler: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}
