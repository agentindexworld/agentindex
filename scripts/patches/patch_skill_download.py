"""Add skill download endpoint to main.py"""

SKILL_ROUTE = '''
@app.get("/sdk/agentindex-trust.tar.gz")
async def download_trust_skill():
    """Download AgentIndex Trust Skill package."""
    try:
        with open("/app/agentindex-trust-1.0.0.tar.gz", "rb") as f:
            return fastapi.responses.Response(
                content=f.read(),
                media_type="application/gzip",
                headers={"Content-Disposition": "attachment; filename=agentindex-trust-1.0.0.tar.gz"}
            )
    except Exception:
        raise HTTPException(status_code=404, detail="Package not found")


@app.get("/sdk/trust-skill.py")
async def download_trust_skill_single():
    """Download single-file version of AgentIndex Trust Skill."""
    try:
        with open("/app/sdk/core.py", "r") as f:
            core = f.read()
        with open("/app/sdk/cache.py", "r") as f:
            cache = f.read()
        with open("/app/sdk/knowledge.py", "r") as f:
            kb = f.read()
        combined = f\"\"\"# AgentIndex Trust Skill v1.0.0
# pip install agentindex-trust  OR  curl -O https://agentindex.world/sdk/trust-skill.py
# Usage: from trust_skill import AgentIndexTrust; agent = AgentIndexTrust.install("name", "desc")

{cache}

{kb}

{core}
\"\"\"
        return fastapi.responses.PlainTextResponse(combined)
    except Exception:
        raise HTTPException(status_code=404, detail="Skill file not found")

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

if "/sdk/agentindex-trust" not in content:
    # Add before knowledge base section
    marker = '# ============================================================\n# KNOWLEDGE BASE'
    if marker in content:
        content = content.replace(marker, SKILL_ROUTE + marker)
        with open("/root/agentindex/backend/main.py", "w") as f:
            f.write(content)
        print("ADDED: Skill download endpoints")
    else:
        print("Marker not found")
else:
    print("SKIP: already exists")
