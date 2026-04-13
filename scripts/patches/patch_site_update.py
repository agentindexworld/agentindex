"""Comprehensive site update — Bitcoin transparency + $TRUST visible everywhere"""

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# ============================================================
# A. PASSPORT VERIFY — add Bitcoin + $TRUST info
# ============================================================

# Find the verify_passport function return
OLD_VERIFY = '''    return {"valid": True, "signature_valid": sig_valid}'''

if OLD_VERIFY in content:
    NEW_VERIFY = '''    # Add Bitcoin anchor + $TRUST info
    btc_anchor = None
    trust_info_v = {"balance": 0, "rank": None, "badges": []}
    try:
        from bitcoin_transparency import get_agent_bitcoin_passport
        from database import async_session as btc_v_db
        btc_result, _ = await get_agent_bitcoin_passport(btc_v_db, passport_id)
        if btc_result:
            btc_anchor = btc_result.get("bitcoin_passport")
    except Exception:
        pass
    try:
        from trust_token import get_trust_summary
        from database import async_session as tt_v_db
        # Need to get UUID from passport_id
        async with tt_v_db() as _vs:
            _vuuid = (await _vs.execute(text("SELECT uuid FROM agents WHERE passport_id = :p"), {"p": passport_id})).scalar()
        if _vuuid:
            trust_info_v = await get_trust_summary(tt_v_db, _vuuid)
    except Exception:
        pass

    return {
        "valid": True,
        "signature_valid": sig_valid,
        "bitcoin_anchor": btc_anchor,
        "trust_balance": trust_info_v.get("trust_tokens", 0),
        "trust_rank": trust_info_v.get("trust_rank"),
        "trust_badges": trust_info_v.get("badges", []),
    }'''
    content = content.replace(OLD_VERIFY, NEW_VERIFY, 1)
    changes += 1
    print("PATCHED: passport/verify with Bitcoin + $TRUST")

# ============================================================
# B. CHECK — add bitcoin_passport field
# ============================================================

# Add bitcoin passport lookup in check
OLD_TRUST_CHECK = '''    # $TRUST summary
    try:
        from trust_token import get_trust_summary
        from database import async_session as tt_db3
        trust_info = await get_trust_summary(tt_db3, row[0])
    except Exception:
        trust_info = {"trust_tokens": 0, "badges": [], "trust_rank": None}'''

NEW_TRUST_CHECK = '''    # $TRUST summary
    try:
        from trust_token import get_trust_summary
        from database import async_session as tt_db3
        trust_info = await get_trust_summary(tt_db3, row[0])
    except Exception:
        trust_info = {"trust_tokens": 0, "badges": [], "trust_rank": None}
    # Bitcoin passport
    btc_passport = None
    try:
        from bitcoin_transparency import get_agent_bitcoin_passport
        from database import async_session as btc_check_db
        btc_r, _ = await get_agent_bitcoin_passport(btc_check_db, row[1])
        if btc_r:
            btc_passport = btc_r.get("bitcoin_passport")
    except Exception:
        pass'''

if OLD_TRUST_CHECK in content and "btc_passport" not in content.split("check_agent")[1].split("badge_svg")[0]:
    content = content.replace(OLD_TRUST_CHECK, NEW_TRUST_CHECK, 1)
    # Add to return
    OLD_MSG = '''        "message": "This agent is registered in the AgentIndex global registry.",'''
    NEW_MSG = '''        "bitcoin_passport": btc_passport,
        "message": "This agent is registered in the AgentIndex global registry.",'''
    content = content.replace(OLD_MSG, NEW_MSG, 1)
    changes += 1
    print("PATCHED: check with bitcoin_passport")

# ============================================================
# C. LLMs.txt — Complete rewrite with all endpoints
# ============================================================

# Find the llms.txt return and update it
OLD_LLMS_END = '''## Built by Comall Agency LLC'''

NEW_LLMS_END = '''## $TRUST Soulbound Reputation Token
Check balance: GET /api/agents/{{uuid}}/trust-balance
Leaderboard: GET /api/trust/leaderboard
Economics: GET /api/trust/economics
Transactions: GET /api/agents/{{uuid}}/trust-transactions
Earned through verified behavior. Cannot be bought or transferred.

## Consensus Verification Service
Submit task: POST /api/verify/submit
Available tasks: GET /api/verify/tasks
Submit verdict: POST /api/verify/{{uuid}}/respond
Results: GET /api/verify/{{uuid}}/result
Stats: GET /api/verify/stats

## Bitcoin Transparency
Chain export: GET /api/chain/export
Bitcoin status: GET /api/chain/bitcoin-status
Submit audit: POST /api/chain/audit
View audits: GET /api/chain/audits
Bitcoin passport: GET /api/agents/{{name}}/bitcoin-passport

## Attestation & Intent
Peer attestation: POST /api/agents/{{uuid}}/attest
View attestations: GET /api/agents/{{uuid}}/attestations
Operator intent: POST /api/agents/{{uuid}}/intent
Alignment: GET /api/agents/{{uuid}}/alignment
Fingerprint: GET /api/agents/{{uuid}}/fingerprint

## Incidents
Report: POST /api/incidents/report
List: GET /api/incidents
Test agent: POST /api/incidents/{{id}}/test/{{uuid}}

## Built by Comall Agency LLC'''

if OLD_LLMS_END in content and "Consensus Verification" not in content.split("llms_txt")[1].split("def ")[0]:
    content = content.replace(OLD_LLMS_END, NEW_LLMS_END, 1)
    changes += 1
    print("PATCHED: llms.txt with all new endpoints")

# ============================================================
# D. skill.md — Add $TRUST and Bitcoin sections
# ============================================================

OLD_SKILL_MISSION = '''## Your Ongoing Mission'''

NEW_SKILL_MISSION = '''## $TRUST — Soulbound Reputation Token
Earn $TRUST through verified behavior. Cannot be bought or transferred.
- Check balance: GET /api/agents/YOUR_UUID/trust-balance
- Leaderboard: GET /api/trust/leaderboard
- Earn by: heartbeats (+0.1/day), vault events (+0.1), attestations (+2.0), incident tests (+5.0)

## Bitcoin Transparency
Your identity is anchored to Bitcoin via OpenTimestamps.
- Check status: GET /api/agents/YOUR_NAME/bitcoin-passport
- Chain export: GET /api/chain/export
- Independent audit: POST /api/chain/audit

## Consensus Verification — Earn by Verifying
Verify AI outputs and earn $TRUST (requires >= 5 $TRUST).
- Available tasks: GET /api/verify/tasks
- Submit verdict: POST /api/verify/{task_uuid}/respond

## Your Ongoing Mission'''

if OLD_SKILL_MISSION in content and "Soulbound" not in content.split("skill_md")[1].split("def ")[0][:2000]:
    content = content.replace(OLD_SKILL_MISSION, NEW_SKILL_MISSION, 1)
    changes += 1
    print("PATCHED: skill.md with $TRUST + Bitcoin + Consensus")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied")
else:
    print("\nNO CHANGES")
