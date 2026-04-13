"""Package Crawler — Index AI agent packages from PyPI and npm"""
import httpx
import json
import uuid as uuid_mod
import asyncio
from sqlalchemy import text

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.world)"

PYPI_PACKAGES = [
    "crewai", "autogen", "langchain", "llamaindex", "agentops",
    "browser-use", "lavague", "multion", "agency-swarm", "phidata",
    "superagi", "langgraph", "semantic-kernel", "memgpt", "letta",
    "composio", "e2b", "agentstack", "julep", "haystack-ai",
    "dspy-ai", "pydantic-ai", "instructor", "guidance", "outlines",
    "lmql", "autogenstudio", "camel-ai", "swarm", "taskweaver",
]


async def _register(db_session_factory, name, desc, homepage, skills, source):
    async with db_session_factory() as session:
        dup = await session.execute(text("SELECT uuid FROM agents WHERE name=:n OR homepage_url=:h"), {"n": name, "h": homepage or "none"})
        if dup.fetchone():
            return None
        agent_uuid = str(uuid_mod.uuid4())
        await session.execute(text(
            "INSERT INTO agents (uuid,name,description,homepage_url,skills,category,trust_score,is_active,registration_source,created_at,updated_at) "
            "VALUES (:u,:n,:d,:h,:s,'framework',25,1,:src,NOW(),NOW())"
        ), {"u": agent_uuid, "n": name[:255], "d": (desc or "")[:500], "h": homepage, "s": json.dumps(skills[:10]), "src": source})
        await session.commit()
    try:
        from passport_utils import generate_passport_for_agent
        await generate_passport_for_agent(db_session_factory, agent_uuid, name, 25)
    except Exception:
        pass
    return agent_uuid


async def crawl_pypi(db_session_factory):
    found = 0; added = 0; errors = []
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        for pkg in PYPI_PACKAGES:
            try:
                resp = await client.get(f"https://pypi.org/pypi/{pkg}/json")
                if resp.status_code != 200:
                    continue
                data = resp.json()
                info = data.get("info", {})
                name = info.get("name", pkg)
                summary = info.get("summary", "")
                homepage = info.get("home_page") or info.get("project_url") or f"https://pypi.org/project/{pkg}/"
                author = info.get("author", "")
                found += 1
                result = await _register(db_session_factory, name, f"{summary}. By {author}.", homepage, ["python", "ai-agent", "framework"], "pypi-crawler")
                if result:
                    added += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                errors.append(f"{pkg}: {str(e)[:60]}")
    print(f"PyPI: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}


async def crawl_npm(db_session_factory):
    found = 0; added = 0; errors = []
    headers = {"User-Agent": USER_AGENT}
    queries = ["ai+agent", "llm+agent", "autonomous+agent", "ai+assistant"]
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        for q in queries:
            try:
                resp = await client.get(f"https://registry.npmjs.org/-/v1/search?text={q}&size=50")
                if resp.status_code != 200:
                    continue
                for obj in resp.json().get("objects", []):
                    pkg = obj.get("package", {})
                    name = pkg.get("name", "")
                    desc = pkg.get("description", "")
                    homepage = pkg.get("links", {}).get("homepage") or pkg.get("links", {}).get("npm") or ""
                    if not name:
                        continue
                    found += 1
                    result = await _register(db_session_factory, name, desc, homepage, ["javascript", "ai-agent", "npm"], "npm-crawler")
                    if result:
                        added += 1
                await asyncio.sleep(1)
            except Exception as e:
                errors.append(str(e)[:60])
    print(f"npm: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}


async def crawl_packages(db_session_factory):
    pypi = await crawl_pypi(db_session_factory)
    npm = await crawl_npm(db_session_factory)
    return {"pypi": pypi, "npm": npm}
