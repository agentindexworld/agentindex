"""Patch main.py — Knowledge Base + Consensus Cache endpoints"""

KB_ROUTES = '''
# ============================================================
# KNOWLEDGE BASE — Distributed agent memory with token savings
# ============================================================

@app.post("/api/knowledge/contribute")
async def knowledge_contribute(request: Request):
    """Contribute to the knowledge base. Earns $TRUST."""
    from knowledge_base import contribute
    from database import async_session as kb_db
    body = await request.json()
    uuid = body.get("contributor_uuid", "")
    if not uuid:
        raise HTTPException(status_code=400, detail="contributor_uuid required")
    result, error = await contribute(
        kb_db, uuid, body.get("topic", ""), body.get("content", ""),
        content_type=body.get("content_type", "fact"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/knowledge/search")
async def knowledge_search(q: str = "", limit: int = 5):
    """Search the knowledge base."""
    from knowledge_base import search_knowledge
    from database import async_session as kb_db
    if not q:
        raise HTTPException(status_code=400, detail="q parameter required")
    return await search_knowledge(kb_db, q, limit=min(limit, 20))


@app.post("/api/knowledge/{knowledge_id}/verify")
async def knowledge_verify(knowledge_id: int, request: Request):
    """Verify a knowledge entry."""
    from knowledge_base import verify_knowledge
    from database import async_session as kb_db
    body = await request.json()
    result, error = await verify_knowledge(
        kb_db, knowledge_id, body.get("verifier_uuid", ""),
        body.get("is_accurate", True), body.get("comment"),
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return result


@app.get("/api/knowledge/{knowledge_id}/use")
async def knowledge_use(knowledge_id: int, user_uuid: str = None):
    """Use a knowledge entry. Contributor earns passive $TRUST."""
    from knowledge_base import use_knowledge
    from database import async_session as kb_db
    result, error = await use_knowledge(kb_db, knowledge_id, user_uuid)
    if error:
        raise HTTPException(status_code=404, detail=error)
    return result


@app.get("/api/knowledge/stats")
async def knowledge_stats():
    """Knowledge base statistics."""
    from knowledge_base import get_knowledge_stats
    from database import async_session as kb_db
    return await get_knowledge_stats(kb_db)

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

marker = '# ============================================================\n# VERIFICATION TOOLKIT'
if marker in content and "/api/knowledge/contribute" not in content:
    content = content.replace(marker, KB_ROUTES + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("ADDED: Knowledge base endpoints")
else:
    print("SKIP or already exists")
