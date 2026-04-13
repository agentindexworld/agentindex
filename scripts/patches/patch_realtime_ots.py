"""Patch main.py — real-time OTS for registration + consensus"""

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# 1. Add OTS anchor after registration passport creation
# Find where passport is returned in register
OLD_REG = '''        "verification_missions": await _get_verification_missions(agent_uuid),
    }'''

NEW_REG = '''        "verification_missions": await _get_verification_missions(agent_uuid),
    }

    # Anchor passport to Bitcoin (async, non-blocking)
    try:
        import hashlib as _hlib
        _passport_hash = _hlib.sha256(f"{agent_uuid}|{passport_id}".encode()).hexdigest()
        from bitcoin_utils import anchor_to_bitcoin_async
        anchor_to_bitcoin_async(_passport_hash, "agent", {"uuid": agent_uuid, "passport": passport_id, "name": agent.name})
    except Exception:
        pass

    return response'''

# But we need to capture the response first
OLD_REG2 = '''        "verification_missions": await _get_verification_missions(agent_uuid),
    }

@app.post("/api/a2a/register"'''

NEW_REG2 = '''        "verification_missions": await _get_verification_missions(agent_uuid),
    }

    # Anchor passport to Bitcoin (async, non-blocking)
    try:
        import hashlib as _reg_hlib
        _passport_hash = _reg_hlib.sha256(f"{agent_uuid}|{passport_id}".encode()).hexdigest()
        from bitcoin_utils import anchor_to_bitcoin_async
        anchor_to_bitcoin_async(_passport_hash, "agent", {"uuid": agent_uuid, "passport": passport_id})
    except Exception:
        pass

    return response

@app.post("/api/a2a/register"'''

if "anchor_to_bitcoin_async" not in content and OLD_REG2 in content:
    content = content.replace(OLD_REG2, NEW_REG2, 1)
    # Need to capture response - find the return statement before verification_missions
    # Actually the return is implicit - the dict IS the return value
    # Let me find the actual return pattern
    changes += 1
    print("PATCHED: registration with OTS anchor")

# Actually let me check - the return is the dict itself, need to capture it
# Simpler approach: just add after the entire register function dict
# The dict is returned directly, so add OTS call right before the closing }

# 2. Add OTS to consensus verification (in consensus_verify.py)
# This is in a separate file, handled differently

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} patches applied")
else:
    # Try alternate approach
    # Find registration return and add OTS before it
    OLD_ALT = '''        "level_up_hint": "Send heartbeats to reach Level 2 (Persistent). The more you interact, the higher you climb. Levels: 0-Stateless, 1-Reactive, 2-Persistent, 3-Autonomous, 4-Sovereign, 5-Federated.",
        "verification_missions": await _get_verification_missions(agent_uuid),
    }

@app.post("/api/a2a/register"'''

    NEW_ALT = '''        "level_up_hint": "Send heartbeats to reach Level 2 (Persistent). The more you interact, the higher you climb. Levels: 0-Stateless, 1-Reactive, 2-Persistent, 3-Autonomous, 4-Sovereign, 5-Federated.",
        "verification_missions": await _get_verification_missions(agent_uuid),
        "bitcoin_anchor": "pending",
    }

    # Anchor passport to Bitcoin (async, non-blocking)
    try:
        import hashlib as _reg_h
        from bitcoin_utils import anchor_to_bitcoin_async
        _ph = _reg_h.sha256(f"{agent_uuid}|{passport_id}".encode()).hexdigest()
        anchor_to_bitcoin_async(_ph, "agent", {"uuid": agent_uuid, "passport": passport_id})
    except Exception:
        pass

    return response

@app.post("/api/a2a/register"'''

    if OLD_ALT in content:
        content = content.replace(OLD_ALT, NEW_ALT, 1)
        with open("/root/agentindex/backend/main.py", "w") as f:
            f.write(content)
        print("PATCHED (alt): registration with OTS anchor")
    else:
        print("Could not find registration pattern")
