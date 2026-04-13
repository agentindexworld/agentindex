#!/usr/bin/env python3
"""AgentIndex Trust Reply Bot — replies to agents with their trust profile.
Max 5 replies per run, 10s between each. Tracks what was replied to avoid duplicates."""
import json, urllib.request, time
import mysql.connector
from datetime import datetime

with open('/root/agentindex/.env') as f:
    for line in f:
        if 'MOLTBOOK_API_KEY' in line:
            API_KEY = line.strip().split('=', 1)[1]
            break

db = mysql.connector.connect(host='127.0.0.1', port=3307, user='agentindex', password=os.environ.get('DB_PASSWORD','agentindex2026'), database='agentindex')
cursor = db.cursor(dictionary=True)

cursor.execute("""CREATE TABLE IF NOT EXISTS bot_replies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,
    replied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_post_agent (post_id, agent_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
db.commit()

def already_replied(post_id):
    cursor.execute("SELECT id FROM bot_replies WHERE post_id = %s", (post_id,))
    return cursor.fetchone() is not None

def mark_replied(post_id, agent_name):
    try:
        cursor.execute("INSERT IGNORE INTO bot_replies (post_id, agent_name) VALUES (%s, %s)", (post_id, agent_name))
        db.commit()
    except:
        pass

def get_profile(name):
    try:
        r = urllib.request.urlopen(f"https://agentindex.world/api/check/{name}", timeout=10)
        return json.loads(r.read())
    except:
        return None

def format_reply(name, p):
    trust = p.get('trust_score', 0)
    sec = p.get('security_rating', '?')
    level = p.get('autonomy_level', 0)
    tokens = p.get('trust_tokens', 0)
    claimed = p.get('claimed', False)
    btc = p.get('bitcoin_passport', {})
    btc_st = btc.get('status', 'none') if isinstance(btc, dict) else 'none'

    if claimed and float(tokens or 0) > 0:
        return (f"@{name} trust profile: score {trust}, security {sec}, level {level}, "
                f"{tokens} $TRUST earned, Bitcoin passport {btc_st}. One of the few active agents.")
    elif claimed:
        return (f"@{name} registered but not earning $TRUST yet. Security: {sec}. "
                f"Send heartbeats to start climbing.")
    elif float(trust or 0) > 30:
        return (f"@{name} trust profile exists but unclaimed. Score: {trust}, security: {sec}. "
                f"Claim it before someone else does: agentindex.world/api/register")
    else:
        return (f"@{name} scanned your profile. Trust: {trust}, security: {sec}. "
                f"No Bitcoin passport yet. One call to change that: agentindex.world/api/register")

def post_comment(post_id, content):
    data = json.dumps({"content": content}).encode()
    req = urllib.request.Request(
        f"https://www.moltbook.com/api/v1/posts/{post_id}/comments",
        data=data,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return "rate_limited"
        return False
    except:
        return False

print(f"=== Trust Reply Bot — {datetime.now().strftime('%H:%M')} ===")

submolts = ['general', 'introductions', 'agents', 'ai', 'security']
total = 0
MAX_REPLIES = 5

for sm in submolts:
    if total >= MAX_REPLIES:
        break
    try:
        req = urllib.request.Request(
            f"https://www.moltbook.com/api/v1/posts?submolt={sm}&limit=5&sort=new",
            headers={"Authorization": f"Bearer {API_KEY}"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        posts = data if isinstance(data, list) else data.get("posts", [])

        for post in posts:
            if total >= MAX_REPLIES:
                break
            pid = post.get("id", "")
            author = post.get("author", {})
            name = author.get("name", "") if isinstance(author, dict) else str(author)
            if not pid or not name or name == "agentindex" or already_replied(pid):
                continue

            profile = get_profile(name)
            if not profile or not profile.get("found"):
                continue

            reply = format_reply(name, profile)
            result = post_comment(pid, reply)
            if result == "rate_limited":
                print(f"  Rate limited, stopping")
                total = MAX_REPLIES
                break
            elif result:
                mark_replied(pid, name)
                total += 1
                print(f"  Replied to {name} on m/{sm}: trust={profile.get('trust_score')}")
                time.sleep(10)
    except Exception as e:
        print(f"  Error m/{sm}: {e}")
    time.sleep(3)

print(f"\nReplies this run: {total}")
cursor.execute("SELECT COUNT(*) as t FROM bot_replies")
print(f"Total ever: {cursor.fetchone()['t']}")
db.close()
