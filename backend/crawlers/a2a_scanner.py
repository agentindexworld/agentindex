"""A2A Agent Card Scanner - Checks known domains for /.well-known/agent.json"""

import httpx
import json
import uuid as uuid_mod

DOMAINS = [
    "google.com", "anthropic.com", "openai.com", "crewai.com", "langchain.com",
    "tavily.com", "manus.im", "devin.ai", "agpt.co", "huggingface.co",
    "perplexity.ai", "mistral.ai", "cohere.com", "together.ai", "groq.com",
    "dify.ai", "n8n.io", "botpress.com", "relevanceai.com", "dust.tt",
    "cursor.com", "replit.com", "vercel.com", "supabase.com", "fireworks.ai",
    "replicate.com", "stability.ai", "jasper.ai", "copy.ai", "phind.com",
    "you.com", "codeium.com", "tabnine.com", "sourcegraph.com", "anyscale.com",
    "modal.com", "activepieces.com", "voiceflow.com", "stack-ai.com", "fixie.ai",
    "wordware.ai", "all-hands.dev", "cognition.ai", "adept.ai", "inflection.ai",
    "character.ai", "poe.com", "claude.ai", "chatgpt.com", "gemini.google.com",
]

USER_AGENT = "AgentIndex-Crawler/1.0 (https://agentindex.io)"
PATHS = ["/.well-known/agent.json", "/.well-known/agent-card.json"]


async def scan_a2a(db_session_factory):
    """Scan known domains for A2A Agent Cards"""
    from sqlalchemy import text

    found = 0
    added = 0
    checked = 0
    errors = []

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=5, headers=headers, follow_redirects=True) as client:
        for domain in DOMAINS:
            checked += 1
            for path in PATHS:
                url = f"https://{domain}{path}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    try:
                        card = resp.json()
                    except Exception:
                        continue

                    if not isinstance(card, dict):
                        continue
                    if not card.get("name"):
                        continue

                    found += 1
                    name = card.get("name", domain)
                    description = card.get("description", f"A2A agent discovered at {domain}")[:500]
                    skills_data = card.get("skills", [])
                    skills = []
                    for s in skills_data:
                        if isinstance(s, dict):
                            skills.append(s.get("name", s.get("id", "")))
                        elif isinstance(s, str):
                            skills.append(s)
                    skills = skills[:10] or ["a2a-compatible"]

                    agent_card_url = url

                    async with db_session_factory() as session:
                        result = await session.execute(
                            text("SELECT uuid FROM agents WHERE agent_card_url = :url OR (name = :name AND provider_name = :provider)"),
                            {"url": agent_card_url, "name": name, "provider": domain},
                        )
                        if result.fetchone():
                            break

                        agent_uuid = str(uuid_mod.uuid4())
                        await session.execute(
                            text(
                                """INSERT INTO agents
                                (uuid, name, description, provider_name, agent_card_url,
                                 homepage_url, skills, category, trust_score,
                                 is_verified, is_active, registration_source,
                                 supported_protocols, created_at, updated_at)
                                VALUES (:uuid, :name, :desc, :provider, :card_url,
                                        :homepage, :skills, 'platform', :trust,
                                        1, 1, 'a2a-discovery',
                                        :protocols, NOW(), NOW())"""
                            ),
                            {
                                "uuid": agent_uuid,
                                "name": name,
                                "desc": description,
                                "provider": domain,
                                "card_url": agent_card_url,
                                "homepage": f"https://{domain}",
                                "skills": json.dumps(skills),
                                "trust": 50,
                                "protocols": json.dumps(["a2a"]),
                            },
                        )
                        await session.commit()
                        added += 1

                    break  # Found card, skip other paths

                except Exception as e:
                    continue

    print(f"🔍 A2A scanner: checked={checked}, found={found}, added={added}")
    return {"found": found, "added": added, "domains_checked": checked, "errors": errors}
