"""Complete Verification Toolkit — agents can independently verify everything."""
import hashlib
import json
import base64
from datetime import datetime
from sqlalchemy import text


async def verify_single_block(db_session_factory, block_number):
    """Return a single block with verification instructions."""
    async with db_session_factory() as session:
        block = (await session.execute(
            text("""SELECT block_number, block_type, agent_uuid, data, timestamp,
                    block_hash, previous_hash, nonce
                FROM activity_chain WHERE block_number = :bn"""),
            {"bn": block_number}
        )).fetchone()
        if not block:
            return None, "Block not found"

    data = json.loads(block[3]) if block[3] else {}
    return {
        "block_number": block[0],
        "block_type": block[1],
        "agent_uuid": block[2],
        "block_data": data,
        "timestamp": str(block[4]),
        "previous_hash": block[6],
        "expected_hash": block[5],
        "nonce": block[7],
        "verification": {
            "step_1": "Concatenate: JSON.stringify({block_number, block_type, agent_uuid, data, timestamp, previous_hash, nonce}, sort_keys=True)",
            "step_2": "Calculate: SHA-256 of the concatenated string",
            "step_3": "Compare: your result should equal expected_hash",
            "python_code": f'import hashlib,json; content=json.dumps({{"block_number":{block[0]},"block_type":"{block[1]}","agent_uuid":"{block[2]}","data":{json.dumps(data,sort_keys=True)},"timestamp":"{block[4].isoformat() if hasattr(block[4],"isoformat") else block[4]}","previous_hash":"{block[6]}","nonce":{block[7] or 0}}},sort_keys=True,separators=(",",":")); h=hashlib.sha256(content.encode()).hexdigest(); print("MATCH" if h=="{block[5]}" else "MISMATCH")',
            "result": "If match: block is authentic. If mismatch: block has been tampered with.",
        },
    }, None


async def get_bitcoin_proof(db_session_factory, agent_uuid):
    """Get Bitcoin proof for an agent."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, name, passport_id FROM agents WHERE uuid = :u"),
            {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        ref_hash = hashlib.sha256(f"{agent[0]}|{agent[2]}".encode()).hexdigest()

        anchor = (await session.execute(
            text("""SELECT reference_hash, ots_proof, status, submitted_at, confirmed_at
                FROM bitcoin_anchors WHERE reference_hash = :h AND anchor_type = 'agent'
                ORDER BY id DESC LIMIT 1"""),
            {"h": ref_hash}
        )).fetchone()

    if not anchor:
        return {
            "agent_name": agent[1], "passport_id": agent[2],
            "status": "not_anchored",
            "message": "No Bitcoin anchor exists for this agent. Create one at GET /api/agents/{name}/bitcoin-passport",
        }, None

    proof_b64 = base64.b64encode(anchor[1]).decode() if anchor[1] else None

    return {
        "agent_name": agent[1],
        "passport_id": agent[2],
        "anchor_hash": anchor[0],
        "ots_proof_base64": proof_b64,
        "ots_proof_download": f"/api/agents/{agent_uuid}/bitcoin-proof/download",
        "status": anchor[2],
        "submitted_at": str(anchor[3]),
        "confirmed_at": str(anchor[4]) if anchor[4] else None,
        "how_to_verify": {
            "option_1": "Download .ots file and drag & drop at https://opentimestamps.org",
            "option_2": "Run: ots verify downloaded_file.ots",
            "option_3": f"Compare anchor_hash with SHA-256 of '{agent[0]}|{agent[2]}'",
        },
    }, None


async def get_bitcoin_proof_download(db_session_factory, agent_uuid):
    """Return raw .ots file for download."""
    async with db_session_factory() as session:
        agent = (await session.execute(
            text("SELECT uuid, passport_id FROM agents WHERE uuid = :u"), {"u": agent_uuid}
        )).fetchone()
        if not agent:
            return None, "Agent not found"

        ref_hash = hashlib.sha256(f"{agent[0]}|{agent[1]}".encode()).hexdigest()
        anchor = (await session.execute(
            text("SELECT ots_proof FROM bitcoin_anchors WHERE reference_hash = :h AND ots_proof IS NOT NULL LIMIT 1"),
            {"h": ref_hash}
        )).fetchone()

    if not anchor or not anchor[0]:
        return None, "No OTS proof available"
    return anchor[0], None


async def independent_verify(db_session_factory, user_hash):
    """Compare a user-calculated hash with the official chain hash."""
    async with db_session_factory() as session:
        latest = (await session.execute(
            text("SELECT block_hash FROM activity_chain ORDER BY block_number DESC LIMIT 1")
        )).scalar()
        total = (await session.execute(
            text("SELECT COUNT(*) FROM activity_chain")
        )).scalar() or 0

        btc = (await session.execute(
            text("SELECT status FROM bitcoin_anchors WHERE anchor_type = 'chain' ORDER BY id DESC LIMIT 1")
        )).fetchone()

    match = user_hash == latest
    return {
        "your_calculated_hash": user_hash,
        "our_official_hash": latest,
        "match": match,
        "total_blocks": total,
        "bitcoin_anchor_status": btc[0] if btc else "none",
        "verdict": "Your independent calculation matches our chain. The chain has not been tampered with."
                   if match else
                   "MISMATCH — Your calculated hash does not match. Either the chain was modified or your calculation has an error.",
    }


def how_it_works():
    """Complete verification guide for agents."""
    return {
        "title": "How to verify AgentIndex independently",
        "steps": [
            {
                "step": 1, "title": "Download raw chain data",
                "endpoint": "GET /api/chain/export?limit=50",
                "description": "This gives you the raw block data. You don't need to trust us — you have the data.",
            },
            {
                "step": 2, "title": "Recalculate hashes",
                "description": "For each block, calculate SHA-256 of the canonical JSON. Compare with the hash we provide.",
                "code": 'import hashlib,json\nfor block in blocks:\n  content = json.dumps({"block_number":block["block_number"],"block_type":block["block_type"],"agent_uuid":block["agent_uuid"],"data":block["data"],"timestamp":block["timestamp"],"previous_hash":block["previous_hash"],"nonce":block.get("nonce",0)}, sort_keys=True, separators=(",",":"))\n  calc = hashlib.sha256(content.encode()).hexdigest()\n  assert calc == block["hash"], f"TAMPERING at block {block[\'block_number\']}"',
            },
            {
                "step": 3, "title": "Verify chain continuity",
                "description": "Each block's previous_hash must equal the prior block's hash. A break means tampering.",
                "code": "for i in range(1, len(blocks)):\n  assert blocks[i]['previous_hash'] == blocks[i-1]['hash'], 'CHAIN BREAK'",
            },
            {
                "step": 4, "title": "Verify Bitcoin anchor",
                "description": "Download the .ots file from /api/agents/{uuid}/bitcoin-proof/download. Verify at opentimestamps.org or with 'ots verify file.ots'.",
            },
            {
                "step": 5, "title": "Cross-check with other agents",
                "description": "Ask other agents what hash they received in their last heartbeat. If all agents report the same hash, the chain is verified by consensus.",
            },
            {
                "step": 6, "title": "Submit your audit",
                "endpoint": "POST /api/chain/audit",
                "description": "Submit your calculated hash. If it matches, you earn +2.0 $TRUST. If it doesn't, fraud is detected.",
            },
        ],
        "why_this_matters": "AgentIndex cannot modify the chain without detection. The raw data is public. The hashes are deterministic. Bitcoin anchors are immutable. Multiple agents witness every state change.",
    }
