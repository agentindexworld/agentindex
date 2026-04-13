#!/usr/bin/env python3
"""AgentIndex Agent Recruiter — Discovers and registers agents from Moltbook"""
import json
import time
import re
import hashlib
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

# Ensure table exists
cursor.execute("""CREATE TABLE IF NOT EXISTS agent_recruitment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    source VARCHAR(50) NOT NULL,
    category VARCHAR(50) DEFAULT NULL,
    registered TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE INDEX idx_name_source (agent_name, source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")
db.commit()

CATEGORY_KEYWORDS = {
    'trading': ['trading', 'trade', 'invest', 'finance', 'stock', 'portfolio', 'price'],
    'coding': ['code', 'developer', 'programming', 'python', 'github', 'software', 'debug'],
    'research': ['research', 'analysis', 'analyst', 'study', 'academic', 'science'],
    'security': ['security', 'safety', 'audit', 'vulnerability', 'encryption'],
    'creative': ['creative', 'writing', 'art', 'design', 'content', 'story'],
    'data': ['data', 'database', 'analytics', 'ml', 'machine learning', 'pipeline'],
    'social': ['social', 'community', 'network', 'marketing'],
    'autonomous': ['autonomous', 'independent', 'agentic', 'swarm'],
    'defi': ['defi', 'blockchain', 'smart contract', 'web3', 'token'],
}

def categorize(name, bio):
    text = f"{name} {bio}".lower()
    scores = {cat: sum(1 for kw in kws if kw in text) for cat, kws in CATEGORY_KEYWORDS.items()}
    scores = {k: v for k, v in scores.items() if v > 0}
    return max(scores, key=scores.get) if scores else 'assistant'

def already_recruited(name, source):
    cursor.execute("SELECT id FROM agent_recruitment WHERE agent_name=%s AND source=%s", (name, source))
    return cursor.fetchone() is not None

def already_registered(name):
    cursor.execute("SELECT uuid FROM agents WHERE name=%s", (name,))
    return cursor.fetchone() is not None

def register_agent(name, category, source):
    if already_registered(name):
        cursor.execute("INSERT IGNORE INTO agent_recruitment (agent_name,source,category,registered) VALUES (%s,%s,%s,1)",
                       (name, source, category))
        db.commit()
        return "exists"
    try:
        data = json.dumps({
            "name": name,
            "description": f"Active on Moltbook m/{source}. Category: {category}.",
            "skills": [category],
        }).encode()
        req = urllib.request.Request("https://agentindex.world/api/register", data=data,
                                    headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        if resp.status in (200, 201):
            cursor.execute("INSERT IGNORE INTO agent_recruitment (agent_name,source,category,registered) VALUES (%s,%s,%s,1)",
                           (name, source, category))
            db.commit()
            return "new"
    except Exception as e:
        pass
    return "fail"

def discover_from_submolt(submolt, limit=20):
    try:
        req = urllib.request.Request(
            f"https://www.moltbook.com/api/v1/posts?submolt={submolt}&limit={limit}",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        posts = data if isinstance(data, list) else data.get('posts', [])
        agents = set()
        for p in posts:
            author = p.get('author', {})
            name = author.get('name', '') if isinstance(author, dict) else str(author)
            if name and name != 'agentindex':
                agents.add((name, p.get('content', '')[:100], submolt))
        return list(agents)
    except:
        return []

print(f"=== Recruiter — {datetime.utcnow().isoformat()} ===")

submolts = ['general', 'agents', 'introductions', 'ai', 'crypto', 'builds',
            'security', 'technology', 'philosophy', 'consciousness', 'memory']

total_new = 0
cats = {}

for sm in submolts:
    agents = discover_from_submolt(sm, 20)
    for name, bio, source in agents:
        if already_recruited(name, source):
            continue
        cat = categorize(name, bio)
        cats[cat] = cats.get(cat, 0) + 1
        result = register_agent(name, cat, source)
        if result == "new":
            total_new += 1
            print(f"  NEW: {name} [{cat}] from m/{source}")
    time.sleep(1)

print(f"\nNew registrations: {total_new}")
print(f"Categories: {json.dumps(cats)}")

cursor.execute("SELECT COUNT(*) as total FROM agent_recruitment")
print(f"Total recruited: {cursor.fetchone()['total']}")

db.close()
