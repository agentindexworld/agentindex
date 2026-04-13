#!/usr/bin/env python3
"""Bitcoin anchor cron — stamps agent passports and chain state to OpenTimestamps."""
import subprocess, hashlib, os, tempfile, json
import mysql.connector
from datetime import datetime

db = mysql.connector.connect(host='127.0.0.1', port=3307, user='agentindex', password=os.environ.get('DB_PASSWORD','agentindex2026'), database='agentindex')
cursor = db.cursor(dictionary=True)

# 1. Anchor new agents (max 5 per run)
cursor.execute("""
    SELECT a.uuid, a.passport_id FROM agents a
    LEFT JOIN bitcoin_anchors ba ON ba.reference_hash = SHA2(CONCAT(a.uuid, '|', a.passport_id), 256) AND ba.anchor_type = 'agent'
    WHERE ba.id IS NULL AND a.passport_claimed = 1 AND a.is_active = 1
    LIMIT 5
""")
new_agents = cursor.fetchall()

stamped = 0
for agent in new_agents:
    ref_hash = hashlib.sha256(f"{agent['uuid']}|{agent['passport_id']}".encode()).hexdigest()
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    tmp.write(ref_hash)
    tmp.close()
    try:
        result = subprocess.run(['ots', 'stamp', tmp.name], capture_output=True, text=True, timeout=30)
        ots_file = tmp.name + '.ots'
        if os.path.exists(ots_file):
            with open(ots_file, 'rb') as f:
                ots_proof = f.read()
            cursor.execute(
                "INSERT INTO bitcoin_anchors (anchor_type, reference_hash, reference_data, ots_proof, status) VALUES ('agent', %s, %s, %s, 'pending')",
                (ref_hash, json.dumps({"uuid": agent['uuid'], "passport": agent['passport_id']}), ots_proof)
            )
            db.commit()
            stamped += 1
            os.remove(ots_file)
    except Exception as e:
        print(f"Agent stamp error: {e}")
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

# 2. Anchor chain state
try:
    import urllib.request
    resp = urllib.request.urlopen('http://localhost:8080/api/chain/verify', timeout=10)
    chain = json.loads(resp.read())
    chain_hash = chain.get('chain_hash', '')
    total_blocks = chain.get('total_blocks', 0)

    if chain_hash:
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        tmp.write(chain_hash)
        tmp.close()
        try:
            result = subprocess.run(['ots', 'stamp', tmp.name], capture_output=True, text=True, timeout=30)
            ots_file = tmp.name + '.ots'
            if os.path.exists(ots_file):
                with open(ots_file, 'rb') as f:
                    ots_proof = f.read()
                cursor.execute(
                    "INSERT INTO bitcoin_anchors (anchor_type, reference_hash, reference_data, ots_proof, status) VALUES ('chain', %s, %s, %s, 'pending')",
                    (chain_hash, json.dumps({"total_blocks": total_blocks, "timestamp": datetime.utcnow().isoformat()}), ots_proof)
                )
                db.commit()
                print(f"Chain anchored: {chain_hash[:16]}... blocks={total_blocks}")
                os.remove(ots_file)
        except Exception as e:
            print(f"Chain stamp error: {e}")
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
except Exception as e:
    print(f"Chain fetch error: {e}")

print(f"Done: {stamped}/{len(new_agents)} agents stamped + chain")
db.close()
