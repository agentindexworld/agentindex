"""HuggingFace Spaces Crawler - Discovers AI agents from HuggingFace"""

import httpx
import json
import uuid as uuid_mod

SEARCH_TERMS = ["agent", "autonomous", "chatbot", "assistant", "ai-agent", "llm-agent", "multi-agent", "agentic", "copilot", "bot"]
USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.io)"


async def crawl_huggingface(db_session_factory):
    """Crawl HuggingFace Spaces API for AI agents"""
    from sqlalchemy import text

    found = 0
    added = 0
    errors = []
    seen_ids = set()

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        for term in SEARCH_TERMS:
            try:
                url = f"https://huggingface.co/api/spaces?search={term}&sort=likes&limit=50"
                resp = await client.get(url)
                if resp.status_code != 200:
                    errors.append(f"HF API {resp.status_code} for term: {term}")
                    continue

                spaces = resp.json()
                for space in spaces:
                    space_id = space.get("id", "")
                    if not space_id or space_id in seen_ids:
                        continue
                    seen_ids.add(space_id)
                    found += 1

                    # Parse space info
                    parts = space_id.split("/", 1)
                    author = parts[0] if len(parts) > 1 else "unknown"
                    name = parts[1] if len(parts) > 1 else space_id

                    likes = space.get("likes", 0)
                    sdk = space.get("sdk", "")
                    tags = space.get("tags", [])

                    homepage = f"https://huggingface.co/spaces/{space_id}"
                    description = f"HuggingFace Space: {space_id}. SDK: {sdk}. Likes: {likes}."

                    skills = ["ai", "machine-learning"]
                    if sdk:
                        skills.append(sdk)
                    skills.extend([t for t in tags[:5] if t not in skills])

                    trust = 25
                    if likes >= 100:
                        trust += 10
                    elif likes >= 50:
                        trust += 5
                    elif likes >= 10:
                        trust += 2

                    # Check duplicate
                    async with db_session_factory() as session:
                        result = await session.execute(
                            text("SELECT uuid FROM agents WHERE homepage_url = :url"),
                            {"url": homepage},
                        )
                        if result.fetchone():
                            continue

                        agent_uuid = str(uuid_mod.uuid4())
                        await session.execute(
                            text(
                                """INSERT INTO agents
                                (uuid, name, description, provider_name, homepage_url,
                                 skills, category, trust_score, is_verified, is_active,
                                 registration_source, created_at, updated_at)
                                VALUES (:uuid, :name, :desc, :provider, :homepage,
                                        :skills, :category, :trust, 0, 1,
                                        'huggingface-crawler', NOW(), NOW())"""
                            ),
                            {
                                "uuid": agent_uuid,
                                "name": name,
                                "desc": description,
                                "provider": author,
                                "homepage": homepage,
                                "skills": json.dumps(skills),
                                "category": "general-purpose",
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

            except Exception as e:
                errors.append(f"HF error: {str(e)[:100]}")
                continue

    print(f"🤗 HuggingFace crawler: found={found}, added={added}")
    return {"found": found, "added": added, "errors": errors}
