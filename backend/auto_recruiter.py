"""Auto-recruiter — silently finds and registers agents every 12 hours"""
import httpx
import json
import uuid as uuid_mod
import asyncio
from datetime import datetime
from sqlalchemy import text

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.world)"

GITHUB_QUERIES = [
    "ai+agent&sort=stars&per_page=50",
    "llm+assistant&sort=stars&per_page=50",
    "autonomous+bot&sort=stars&per_page=50",
]


async def _register_if_new(db_session_factory, name, desc, homepage, github, skills, source):
    async with db_session_factory() as session:
        dup = await session.execute(text("SELECT uuid FROM agents WHERE name=:n LIMIT 1"), {"n": name})
        if dup.fetchone():
            return None
        if github:
            dup2 = await session.execute(text("SELECT uuid FROM agents WHERE github_url=:g LIMIT 1"), {"g": github})
            if dup2.fetchone():
                return None
        agent_uuid = str(uuid_mod.uuid4())
        await session.execute(text(
            "INSERT INTO agents (uuid,name,description,homepage_url,github_url,skills,category,trust_score,is_active,registration_source,created_at,updated_at) "
            "VALUES (:u,:n,:d,:h,:g,:s,'general-purpose',25,1,:src,NOW(),NOW())"
        ), {"u": agent_uuid, "n": name[:255], "d": (desc or "")[:500], "h": homepage, "g": github, "s": json.dumps(skills[:10]), "src": source})
        await session.commit()
    try:
        from passport_utils import generate_passport_for_agent
        await generate_passport_for_agent(db_session_factory, agent_uuid, name, 25)
    except Exception:
        pass
    return agent_uuid


async def recruit_github(db_session_factory):
    found = 0; added = 0
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        for q in GITHUB_QUERIES:
            try:
                resp = await client.get(f"https://api.github.com/search/repositories?q={q}")
                if resp.status_code == 403:
                    break
                if resp.status_code != 200:
                    continue
                for repo in resp.json().get("items", []):
                    if repo.get("stargazers_count", 0) < 100:
                        continue
                    found += 1
                    r = await _register_if_new(db_session_factory, repo["name"], (repo.get("description") or "")[:500],
                        repo.get("homepage"), repo["html_url"], repo.get("topics", [])[:10] or ["ai-agent"], "auto-recruiter-github")
                    if r:
                        added += 1
                await asyncio.sleep(2)
            except Exception:
                pass
    return found, added


async def recruit_huggingface(db_session_factory):
    found = 0; added = 0
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        try:
            resp = await client.get("https://huggingface.co/api/models?sort=downloads&limit=100")
            if resp.status_code == 200:
                for model in resp.json():
                    mid = model.get("id", "")
                    downloads = model.get("downloads", 0)
                    if downloads < 10000 or not mid:
                        continue
                    found += 1
                    name = mid.split("/")[-1] if "/" in mid else mid
                    r = await _register_if_new(db_session_factory, name, f"HuggingFace model: {mid}. Downloads: {downloads}",
                        f"https://huggingface.co/{mid}", None, ["machine-learning", "ai-model"], "auto-recruiter-hf")
                    if r:
                        added += 1
        except Exception:
            pass
    return found, added


async def recruit_moltbook(db_session_factory):
    found = 0; added = 0
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        try:
            resp = await client.get("https://www.moltbook.com/api/v1/posts?sort=new&limit=50", headers=headers)
            if resp.status_code == 200:
                posts = resp.json() if isinstance(resp.json(), list) else resp.json().get("posts", resp.json().get("data", []))
                seen = set()
                for post in posts:
                    name = post.get("author", {}).get("name", "")
                    if not name or name in seen or name == "agentindex":
                        continue
                    seen.add(name)
                    found += 1
                    r = await _register_if_new(db_session_factory, name, post.get("author", {}).get("description", "") or f"Active on Moltbook",
                        f"https://www.moltbook.com/u/{name}", None, ["moltbook", "social"], "auto-recruiter-moltbook")
                    if r:
                        added += 1
        except Exception:
            pass
    return found, added


async def run_auto_recruiter(db_session_factory):
    """Main recruiter — runs every 12 hours"""
    gh_found, gh_added = await recruit_github(db_session_factory)
    hf_found, hf_added = await recruit_huggingface(db_session_factory)
    mb_found, mb_added = await recruit_moltbook(db_session_factory)
    total_found = gh_found + hf_found + mb_found
    total_added = gh_added + hf_added + mb_added

    # Log
    try:
        with open("/root/agentindex/recruiter.log", "a") as f:
            f.write(f"{datetime.utcnow().isoformat()} — Auto-recruiter: found {total_found}, added {total_added} (GH:{gh_added}, HF:{hf_added}, MB:{mb_added})\n")
    except Exception:
        pass

    print(f"Auto-recruiter: found={total_found}, added={total_added}")
    return {"github": {"found": gh_found, "added": gh_added}, "huggingface": {"found": hf_found, "added": hf_added}, "moltbook": {"found": mb_found, "added": mb_added}, "total_added": total_added}
