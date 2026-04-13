"""Bitcoin utility — async OTS stamping for critical events"""
import subprocess
import tempfile
import os
import threading
import json


def anchor_to_bitcoin_async(reference_hash, anchor_type, reference_data=None):
    """Submit a hash to OpenTimestamps in background thread. Non-blocking."""
    def _anchor():
        try:
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            tmp.write(reference_hash)
            tmp.close()

            result = subprocess.run(
                ['ots', 'stamp', tmp.name],
                capture_output=True, text=True, timeout=30
            )

            ots_file = tmp.name + '.ots'
            ots_proof = None
            if os.path.exists(ots_file):
                with open(ots_file, 'rb') as f:
                    ots_proof = f.read()
                os.remove(ots_file)

            import mysql.connector
            db = mysql.connector.connect(
                host='db', port=3306,
                user='agentindex', password=os.getenv('DB_PASSWORD', 'agentindex2026'),
                database='agentindex'
            )
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO bitcoin_anchors (anchor_type, reference_hash, reference_data, ots_proof, status) VALUES (%s, %s, %s, %s, 'pending')",
                (anchor_type, reference_hash, json.dumps(reference_data) if reference_data else None, ots_proof)
            )
            db.commit()
            db.close()
            os.remove(tmp.name)
        except Exception as e:
            print(f"OTS anchor error ({anchor_type}): {e}")

    thread = threading.Thread(target=_anchor, daemon=True)
    thread.start()
