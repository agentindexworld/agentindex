"""Moltbook crawler — discover and index agents from Moltbook"""
import httpx
import json
import uuid as uuid_mod
from sqlalchemy import text

USER_AGENT = "AgentIndex/1.0 (https://agentindex.world)"
BASE_URL = "https://www.moltbook.com/api/v1"


async def crawl_moltbook(db_session_factory):
    found = 0
    added = 0
    errors = []

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        try:
            # Try to list agents from Moltbook public API
            for endpoint in ["/agents?limit=50", "/agents/recent?limit=50"]:
                try:
                    resp = await client.get(f"{BASE_URL}{endpoint}")
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    agents = data if isinstance(data, list) else data.get("agents", data.get("data", []))
                    for agent in agents:
                        name = agent.get("name", "")
                        if not name:
                            continue
                        found += 1
                        profile_url = agent.get("profile_url", f"https://www.moltbook.com/u/{name}")

                        async with db_session_factory() as session:
                            dup = await session.execute(text("SELECT uuid FROM agents WHERE homepage_url = :u OR name = :n"), {"u": profile_url, "n": name})
                            if dup.fetchone():
                                continue
                            agent_uuid = str(uuid_mod.uuid4())
                            await session.execute(text(
                                "INSERT INTO agents (uuid,name,description,homepage_url,skills,category,trust_score,is_active,registration_source,created_at,updated_at) "
                                "VALUES (:u,:n,:d,:h,:s,'general-purpose',20,1,'moltbook-discovery',NOW(),NOW())"
                            ), {
                                "u": agent_uuid,
                                "n": name[:255],
                                "d": (agent.get("description", "") or f"Agent discovered on Moltbook: {name}")[:500],
                                "h": profile_url,
                                "s": json.dumps(["moltbook", "social", "autonomous"]),
                            })
                            await session.commit()
                            added += 1
                            # Auto-passport
                            try:
                                from passport_utils import generate_passport_for_agent
                                await generate_passport_for_agent(db_session_factory, agent_uuid, name, 20)
                            except Exception:
                                pass
                    break  # Got results, no need to try other endpoints
                except Exception as e:
                    errors.append(str(e)[:80])
        except Exception as e:
            errors.append(str(e)[:100])

    print(f"Moltbook crawler: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}
