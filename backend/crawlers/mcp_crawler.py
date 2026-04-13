"""MCP Server directories crawler"""
import httpx, json, uuid as uuid_mod, re, asyncio
from sqlalchemy import text

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.io)"

MCP_SOURCES = [
    ("https://mcp.so", "mcp.so"),
    ("https://smithery.ai", "smithery.ai"),
    ("https://glama.ai/mcp/servers", "glama.ai"),
]

async def crawl_mcp(db_session_factory):
    found = 0; added = 0; errors = []
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
        for url, source in MCP_SOURCES:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    errors.append(f"{source} returned {resp.status_code}")
                    continue
                html = resp.text
                # Extract links to MCP servers/packages
                gh_links = re.findall(r'href="(https://github\.com/[\w\-]+/[\w\-]+)"', html)
                names_raw = re.findall(r'<h[23][^>]*>([^<]{3,80})</h[23]>', html)
                seen = set()
                for i, gh in enumerate(gh_links[:30]):
                    if gh in seen: continue
                    seen.add(gh); found += 1
                    name = gh.split("/")[-1]
                    if i < len(names_raw):
                        name = re.sub(r'<[^>]+>', '', names_raw[i]).strip()[:255] or name
                    async with db_session_factory() as session:
                        dup = await session.execute(text("SELECT uuid FROM agents WHERE github_url = :u"), {"u": gh})
                        if dup.fetchone(): continue
                        await session.execute(text(
                            "INSERT INTO agents (uuid,name,description,github_url,skills,category,trust_score,is_active,registration_source,created_at,updated_at) "
                            "VALUES (:u,:n,:d,:g,:s,'general-purpose',22,1,'mcp-crawler',NOW(),NOW())"
                        ), {"u": str(uuid_mod.uuid4()), "n": name[:255], "d": f"MCP server from {source}", "g": gh, "s": json.dumps(["mcp", "tool-use", "integration"])})
                        await session.commit(); added += 1
                await asyncio.sleep(1)
            except Exception as e:
                errors.append(f"{source}: {str(e)[:80]}")
    print(f"🔌 MCP crawler: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}
