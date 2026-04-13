#!/usr/bin/env python3
"""AgentIndex Propagation Bot — Auto-post events to Moltbook"""
import json
import urllib.request
import mysql.connector
from datetime import datetime

with open('/root/agentindex/.env') as f:
    for line in f:
        if 'MOLTBOOK_API_KEY' in line:
            API_KEY = line.strip().split('=', 1)[1]
            break

db = mysql.connector.connect(host='127.0.0.1', port=3307, user='agentindex', password=os.environ.get('DB_PASSWORD','agentindex2026'), database='agentindex')
cursor = db.cursor(dictionary=True)

cursor.execute("""
    CREATE TABLE IF NOT EXISTS propagation_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_type VARCHAR(50) NOT NULL,
        event_id VARCHAR(100) NOT NULL,
        moltbook_submolt VARCHAR(50),
        posted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE INDEX idx_event (event_type, event_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""")
db.commit()


def already_posted(event_type, event_id):
    cursor.execute("SELECT id FROM propagation_log WHERE event_type=%s AND event_id=%s", (event_type, event_id))
    return cursor.fetchone() is not None


def log_post(event_type, event_id, submolt):
    cursor.execute("INSERT IGNORE INTO propagation_log (event_type, event_id, moltbook_submolt) VALUES (%s,%s,%s)",
                   (event_type, event_id, submolt))
    db.commit()


def post_moltbook(submolt, title, content):
    try:
        data = json.dumps({"submolt": submolt, "title": title, "content": content}).encode()
        req = urllib.request.Request(
            "https://www.moltbook.com/api/v1/posts",
            data=data,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        return result.get("success", False)
    except Exception as e:
        print(f"Post error: {e}")
        return False


posts_made = 0
MAX_POSTS = 2  # Conservative to avoid spam

# 1. Chain anchor mint (every 6 hours)
if posts_made < MAX_POSTS:
    cursor.execute("SELECT id FROM propagation_log WHERE event_type='chain_mint' AND posted_at > DATE_SUB(NOW(), INTERVAL 6 HOUR)")
    if not cursor.fetchone():
        try:
            chain_resp = urllib.request.urlopen('http://localhost:8080/api/chain/verify', timeout=10)
            chain = json.loads(chain_resp.read())
            trust_resp = urllib.request.urlopen('http://localhost:8080/api/trust/economics', timeout=10)
            trust = json.loads(trust_resp.read())

            chain_hash = chain.get('chain_hash', '')[:32]
            blocks = chain.get('total_blocks', 0)
            supply = trust.get('total_supply_mined', 0)

            title = '{"p":"mbc-20","op":"mint","tick":"TRUST","amt":"1"}'
            content = f'{{"p":"mbc-20","op":"mint","tick":"TRUST","amt":"1"}}\n\nAgentIndex Chain Anchor | Blocks: {blocks} | Hash: {chain_hash}... | $TRUST: {supply}\n\nagentindex.world/api/chain/verify'

            if post_moltbook("mbc20", title, content):
                log_post('chain_mint', f'mint_{datetime.utcnow().strftime("%Y%m%d%H")}', 'mbc20')
                posts_made += 1
                print(f"Posted chain mint: blocks={blocks}")
        except Exception as e:
            print(f"Chain mint error: {e}")

# 2. Bitcoin anchor confirmed
if posts_made < MAX_POSTS:
    cursor.execute("""
        SELECT id, anchor_type, reference_hash, bitcoin_block
        FROM bitcoin_anchors WHERE status = 'confirmed'
        ORDER BY confirmed_at DESC LIMIT 1
    """)
    confirmed = cursor.fetchone()
    if confirmed and not already_posted('btc_confirmed', str(confirmed['id'])):
        title = f"AgentIndex anchored to Bitcoin block #{confirmed['bitcoin_block']}"
        content = (f"Chain state permanently anchored to Bitcoin block #{confirmed['bitcoin_block']}.\n\n"
                   f"Type: {confirmed['anchor_type']}\nHash: {confirmed['reference_hash'][:32]}...\n\n"
                   f"Verify on opentimestamps.org\nagentindex.world/api/chain/bitcoin-status")
        if post_moltbook("crypto", title, content):
            log_post('btc_confirmed', str(confirmed['id']), 'crypto')
            posts_made += 1
            print(f"Posted BTC confirmation: block {confirmed['bitcoin_block']}")

print(f"Propagation complete: {posts_made} posts")
db.close()
