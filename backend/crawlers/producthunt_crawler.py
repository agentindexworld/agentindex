"""Product Hunt AI launches crawler"""
import httpx, json, uuid as uuid_mod, re
from sqlalchemy import text

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.io)"

async def crawl_producthunt(db_session_factory):
    found = 0; added = 0; errors = []
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
        try:
            resp = await client.get("https://www.producthunt.com/topics/artificial-intelligence")
            if resp.status_code != 200:
                return {"found": 0, "added": 0, "errors": [f"PH returned {resp.status_code}"]}
            # Extract product names and URLs from HTML
            names = re.findall(r'data-test="post-name"[^>]*>([^<]+)<', resp.text)
            taglines = re.findall(r'data-test="post-tagline"[^>]*>([^<]+)<', resp.text)
            links = re.findall(r'href="(/posts/[^"]+)"', resp.text)
            seen = set()
            for i, link in enumerate(links[:50]):
                url = f"https://www.producthunt.com{link}"
                if url in seen: continue
                seen.add(url); found += 1
                name = names[i] if i < len(names) else link.split("/")[-1]
                desc = taglines[i] if i < len(taglines) else f"AI product from Product Hunt"
                async with db_session_factory() as session:
                    dup = await session.execute(text("SELECT uuid FROM agents WHERE homepage_url = :u"), {"u": url})
                    if dup.fetchone(): continue
                    await session.execute(text(
                        "INSERT INTO agents (uuid,name,description,homepage_url,skills,category,trust_score,is_active,registration_source,created_at,updated_at) "
                        "VALUES (:u,:n,:d,:h,:s,'general-purpose',20,1,'producthunt-crawler',NOW(),NOW())"
                    ), {"u": str(uuid_mod.uuid4()), "n": name[:255], "d": desc[:500], "h": url, "s": json.dumps(["ai", "product"])})
                    await session.commit(); added += 1
        except Exception as e:
            errors.append(str(e)[:100])
    print(f"🏆 ProductHunt: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}
