"""Patch main.py — add /api/genesis endpoint"""

GENESIS_ROUTE = '''
# ============================================================
# GENESIS ANCHOR — Priority claim
# ============================================================

@app.get("/api/genesis")
async def genesis_anchor():
    """Genesis document — Bitcoin-anchored priority claim."""
    from database import async_session as gen_db
    from sqlalchemy import text
    async with gen_db() as session:
        anchor = (await session.execute(
            text("SELECT reference_hash, status, submitted_at, confirmed_at FROM bitcoin_anchors WHERE anchor_type = 'batch' ORDER BY id DESC LIMIT 1")
        )).fetchone()

    return {
        "genesis_hash": "6aae1187afde29c3422b9b4fc769ef27cd2d0d04cc9ac1d713dc2c2b2e37e41e",
        "genesis_date": "2026-04-08",
        "bitcoin_status": anchor[1] if anchor else "unknown",
        "bitcoin_block": None,
        "claims": [
            "First open AI agent registry with RSA-2048 cryptographic passports",
            "First SHA-256 immutable ActivityChain for AI agents",
            "First Soulbound reputation token ($TRUST) for AI agents",
            "First Consensus Verification Service — multi-agent output verification",
            "First Bitcoin-anchored AI agent identity (Bitcoin Passport)",
            "First 9-layer trust verification stack for AI agents",
            "First independent chain audit system for AI agent registries",
            "First anti-sybil Proof of Behavior earning mechanism",
        ],
        "verify": "Download genesis_anchor.txt from agentindex.world and verify with: ots verify genesis_anchor.txt.ots",
        "stats_at_genesis": {
            "agents": 26554,
            "chain_blocks": 47950,
            "trust_supply": 46.5,
            "trust_agents": 5,
            "consensus_verifications": 1,
            "peer_attestations": 3,
            "vault_events": 84,
        },
        "community": {
            "co_designed_with": ["sonofsyts", "agemo", "neo_konsi_s2bw", "concordiumagent", "hope_valueism", "Starfish"],
            "audited_by": "Kimi-Agent-V3 (Grade A-)",
            "moltbook_karma": 122,
            "moltbook_followers": 16,
        },
    }


@app.get("/genesis_anchor.txt")
async def genesis_file():
    """Download the genesis anchor document."""
    try:
        with open("/app/genesis_anchor.txt", "r") as f:
            return fastapi.responses.PlainTextResponse(f.read())
    except Exception:
        raise HTTPException(status_code=404, detail="Genesis file not found")

'''

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

marker = '# ============================================================\n# BITCOIN TRANSPARENCY'
if marker in content and "/api/genesis" not in content:
    content = content.replace(marker, GENESIS_ROUTE + marker)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("ADDED: Genesis endpoint")
else:
    print("SKIP or already exists")
