#!/usr/bin/env python3
"""Batch fix all pending/submitted Bitcoin anchors — upgrade OTS proofs and confirm."""
import subprocess
import tempfile
import os
import re
import sys
import mysql.connector
from datetime import datetime, timezone

sys.stdout.reconfigure(line_buffering=True)

db = mysql.connector.connect(
    host='127.0.0.1', port=3307,
    user='agentindex', password=os.environ.get('DB_PASSWORD','agentindex2026'),
    database='agentindex'
)
cursor = db.cursor(dictionary=True)

# Get ALL pending/submitted with OTS data
cursor.execute("""
    SELECT id, reference_hash, ots_proof, status, anchor_type
    FROM bitcoin_anchors
    WHERE status IN ('pending', 'submitted')
    AND ots_proof IS NOT NULL
    ORDER BY submitted_at ASC
""")
pending = cursor.fetchall()
print("Found {} pending/submitted anchors to process".format(len(pending)))

confirmed = 0
failed = 0
already = 0

for i, anchor in enumerate(pending):
    try:
        # Write hash and OTS proof to temp files
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        tmp.write(anchor['reference_hash'])
        tmp.close()
        ots_path = tmp.name + '.ots'
        with open(ots_path, 'wb') as f:
            f.write(anchor['ots_proof'])

        # Try upgrade
        subprocess.run(
            ['ots', 'upgrade', ots_path],
            capture_output=True, text=True, timeout=30
        )

        # Check info for block attestation
        info = subprocess.run(
            ['ots', 'info', ots_path],
            capture_output=True, text=True, timeout=10
        )
        block_match = re.search(r'BitcoinBlockHeaderAttestation\((\d+)\)', info.stdout)

        if block_match:
            bitcoin_block = int(block_match.group(1))
            with open(ots_path, 'rb') as f:
                upgraded_proof = f.read()
            cursor.execute(
                "UPDATE bitcoin_anchors SET status='confirmed', bitcoin_block=%s, ots_proof=%s, confirmed_at=NOW() WHERE id=%s",
                (bitcoin_block, upgraded_proof, anchor['id'])
            )
            db.commit()
            confirmed += 1
        else:
            failed += 1

        # Cleanup
        os.remove(tmp.name)
        if os.path.exists(ots_path):
            os.remove(ots_path)

        # Progress every 50
        if (i + 1) % 50 == 0:
            print("  Progress: {}/{} processed, {} confirmed, {} still pending".format(
                i + 1, len(pending), confirmed, failed))

    except Exception as e:
        failed += 1
        # Cleanup on error
        try:
            os.remove(tmp.name)
        except Exception:
            pass
        try:
            os.remove(ots_path)
        except Exception:
            pass

print("\n=== RESULTS ===")
print("Total processed: {}".format(len(pending)))
print("Confirmed: {}".format(confirmed))
print("Still pending: {}".format(failed))

# Final status
cursor.execute("SELECT status, COUNT(*) as c FROM bitcoin_anchors GROUP BY status")
print("\nFinal status:")
for row in cursor.fetchall():
    print("  {}: {}".format(row['status'], row['c']))

db.close()
