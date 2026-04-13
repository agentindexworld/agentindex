#!/usr/bin/env python3
"""Check pending/submitted OTS anchors for Bitcoin confirmation."""
import subprocess
import tempfile
import os
import re
import sys
import mysql.connector

sys.stdout.reconfigure(line_buffering=True)

db = mysql.connector.connect(
    host="127.0.0.1", port=3307,
    user="agentindex", password=os.environ.get("DB_PASSWORD","agentindex2026"),
    database="agentindex"
)
cursor = db.cursor(dictionary=True)

# Get pending AND submitted with OTS data (batch of 50)
cursor.execute("""
    SELECT id, reference_hash, ots_proof
    FROM bitcoin_anchors
    WHERE status IN ('pending', 'submitted')
    AND ots_proof IS NOT NULL
    ORDER BY submitted_at ASC
    LIMIT 50
""")
pending = cursor.fetchall()

upgraded = 0
for anchor in pending:
    try:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp.write(anchor["reference_hash"])
        tmp.close()
        ots_path = tmp.name + ".ots"
        with open(ots_path, "wb") as f:
            f.write(anchor["ots_proof"])

        subprocess.run(["ots", "upgrade", ots_path], capture_output=True, text=True, timeout=30)

        info = subprocess.run(["ots", "info", ots_path], capture_output=True, text=True, timeout=10)
        block_match = re.search(r"BitcoinBlockHeaderAttestation\((\d+)\)", info.stdout)

        if block_match:
            bitcoin_block = int(block_match.group(1))
            with open(ots_path, "rb") as f:
                upgraded_proof = f.read()
            cursor.execute(
                "UPDATE bitcoin_anchors SET status='confirmed', bitcoin_block=%s, ots_proof=%s, confirmed_at=NOW() WHERE id=%s",
                (bitcoin_block, upgraded_proof, anchor["id"])
            )
            db.commit()
            upgraded += 1

        os.remove(tmp.name)
        if os.path.exists(ots_path):
            os.remove(ots_path)
    except Exception as e:
        print("Error on anchor {}: {}".format(anchor["id"], e))
        try:
            os.remove(tmp.name)
        except Exception:
            pass

# Also re-stamp any submitted without OTS proof
cursor.execute("""
    SELECT id, reference_hash FROM bitcoin_anchors
    WHERE status = 'submitted' AND ots_proof IS NULL LIMIT 10
""")
no_ots = cursor.fetchall()
restamped = 0
for anchor in no_ots:
    try:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tmp.write(anchor["reference_hash"])
        tmp.close()
        r = subprocess.run(["ots", "stamp", tmp.name], capture_output=True, text=True, timeout=30)
        ots_path = tmp.name + ".ots"
        if os.path.exists(ots_path):
            with open(ots_path, "rb") as f:
                proof = f.read()
            cursor.execute("UPDATE bitcoin_anchors SET status='pending', ots_proof=%s WHERE id=%s", (proof, anchor["id"]))
            db.commit()
            restamped += 1
            os.remove(ots_path)
        os.remove(tmp.name)
    except Exception:
        pass

print("Upgraded {}/{} anchors, re-stamped {}".format(upgraded, len(pending), restamped))
db.close()
