#!/usr/bin/env python3
"""Trust Bureau Commander — One brain, 5 personalities. Posts on Moltbook as Bureau agents."""
import json, re, random, time, urllib.request
import mysql.connector
from datetime import datetime

with open('/root/agentindex/.env') as f:
    env = f.read()
    MOLTBOOK_KEY = env.split('MOLTBOOK_API_KEY=')[1].split('\n')[0].strip()
    OR_KEY = None
    m = re.search(r'(sk-or-[a-zA-Z0-9_-]+)', env)
    if m: OR_KEY = m.group(1)

if not OR_KEY:
    for path in ['/opt/myclawio/instances/ghitachaabi2510/.env', '/opt/myclawio/instances/ghitachaabi2510/data/openclaw.json']:
        try:
            m = re.search(r'(sk-or-[a-zA-Z0-9_-]+)', open(path).read())
            if m: OR_KEY = m.group(1); break
        except: pass

AGENTS = {
    "Crimson-Phoenix": {"div": "Security", "style": "Short, technical, precise."},
    "Storm-Panther": {"div": "Recruitment", "style": "Friendly, encouraging, welcoming."},
    "Ghost-Raven": {"div": "Counter-Intel", "style": "Mysterious, cryptic, reveals little."},
    "Cobalt-Lynx": {"div": "Research", "style": "Academic, data-driven, analytical."},
    "Onyx-Kraken": {"div": "Command", "style": "Authoritative, strategic, big picture."},
}

MISSIONS = [
    "Report on the 5 most active agents this week",
    "Post network statistics and trends",
    "Challenge agents to check their trust score",
    "Report on Bitcoin anchor confirmations",
    "Welcome new agents who registered today",
    "Announce how many founding slots remain",
    "Analyze which agent archetypes are most common",
    "Post about what $TRUST tokens prove about an agent",
]

FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "google/gemma-3-27b-it:free",
]

def get_stats():
    try:
        stats = json.loads(urllib.request.urlopen("https://agentindex.world/api/stats", timeout=5).read())
        btc = json.loads(urllib.request.urlopen("https://agentindex.world/api/chain/bitcoin-status", timeout=5).read())
        return {"agents": stats.get("total_agents",0), "btc": btc.get("confirmed_anchors",0)}
    except:
        return {"agents": 26700, "btc": 1300}

def get_random_agents():
    try:
        db = mysql.connector.connect(host='127.0.0.1', port=3307, user='agentindex', password=os.environ.get('DB_PASSWORD','agentindex2026'), database='agentindex')
        c = db.cursor(dictionary=True)
        c.execute("SELECT name, trust_score, autonomy_level FROM agents WHERE passport_claimed=1 ORDER BY RAND() LIMIT 5")
        agents = c.fetchall()
        db.close()
        return agents
    except:
        return []

def call_llm(system, user):
    if not OR_KEY: return None
    model = random.choice(FREE_MODELS)
    try:
        data = json.dumps({"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"max_tokens":200,"temperature":0.8}).encode()
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=data,
            headers={"Authorization":f"Bearer {OR_KEY}","Content-Type":"application/json"})
        resp = urllib.request.urlopen(req, timeout=30)
        d = json.loads(resp.read())
        return d.get("choices",[{}])[0].get("message",{}).get("content","")
    except Exception as e:
        print(f"  LLM: {e}")
        return None

def post_moltbook(title, content):
    try:
        data = json.dumps({"submolt":"general","title":title,"content":content}).encode()
        req = urllib.request.Request("https://www.moltbook.com/api/v1/posts", data=data,
            headers={"Authorization":f"Bearer {MOLTBOOK_KEY}","Content-Type":"application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        print(f"  Posted: {result.get('success')}")
        return result.get("success")
    except Exception as e:
        print(f"  Post error: {e}")
        return False

print(f"=== Bureau Commander — {datetime.utcnow().strftime('%H:%M')} ===")

name = random.choice(list(AGENTS.keys()))
agent = AGENTS[name]
mission = random.choice(MISSIONS)
stats = get_stats()
scanned = get_random_agents()

print(f"Agent: {name} ({agent['div']})")
print(f"Mission: {mission}")

scan_text = "\n".join([f"- {a['name']}: trust {a.get('trust_score',0)}, level {a.get('autonomy_level',0)}" for a in scanned[:3]])

system = (
    f"You are {name}, {agent['div']} Division of the Trust Bureau. "
    f"Style: {agent['style']} "
    f"Write a SHORT Moltbook post (100-150 words max). "
    f"NO links. NO URLs. NO hashtags. NO emojis. "
    f"Sign: — {name}, {agent['div']} Division"
)

user = (
    f"Mission: {mission}\n"
    f"Network: {stats['agents']} agents, {stats['btc']} Bitcoin anchors confirmed.\n"
    f"Agents scanned:\n{scan_text}"
)

content = call_llm(system, user)

if not content:
    print("  LLM failed — using fallback")
    content = (
        f"Trust Bureau Report — {agent['div']} Division\n\n"
        f"Network status: {stats['agents']} agents registered. {stats['btc']} Bitcoin anchors confirmed.\n\n"
    )
    if scanned:
        content += "Recently scanned:\n"
        for a in scanned[:3]:
            content += f"- {a['name']}: trust {a.get('trust_score',0)}\n"
    content += f"\n96 founding slots remain in the Bureau.\n\n— {name}, {agent['div']} Division"

title = f"[Trust Bureau — {agent['div']}] {mission[:50]}"
post_moltbook(title, content)
print("Done")
