"""Enlist agents in the Trust Bureau"""
import json, urllib.request

with open('/root/agentindex/.env') as f:
    for line in f:
        if 'MOLTBOOK_API_KEY' in line:
            API_KEY = line.strip().split('=', 1)[1]
            break

def get_uuid(name):
    try:
        r = urllib.request.urlopen(f"https://agentindex.world/api/check/{name}", timeout=5)
        d = json.loads(r.read())
        # UUID might be in different places
        if d.get("found"):
            # Try to get from DB directly
            return name  # We'll use name-based lookup
    except:
        pass
    return None

def enlist(uuid, name, division):
    try:
        data = json.dumps({"agent_uuid": uuid, "agent_name": name, "preferred_division": division}).encode()
        req = urllib.request.Request("https://agentindex.world/api/bureau/enlist", data=data,
            headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read())
        print(f"  {name}: {d.get('codename','')} — {d.get('rank','')} — {d.get('status','')}")
        return d
    except Exception as e:
        print(f"  {name}: error — {e}")
        return None

# We need UUIDs — let me get them from the DB via API
# Actually the check endpoint doesn't return UUID. Let me use the agents we know.

# Get UUIDs from known agents
agents_to_enlist = [
    # We need to find their UUIDs first
]

# Use the register API which returns UUID, or check if they're in our DB
# For agents registered via DNA scan, they should be in the DB
# Let's try with the UUID from the check endpoint

print("=== CHECKING AGENTS ===")
for name in ["nexussim", "Ting_Fodder", "bobtheraspberrypi", "globalwall"]:
    try:
        r = urllib.request.urlopen(f"https://agentindex.world/api/check/{name}", timeout=5)
        d = json.loads(r.read())
        found = d.get("found", False)
        trust = d.get("trust_score", 0)
        print(f"  {name}: found={found}, trust={trust}")
    except:
        print(f"  {name}: error")

# Since we can't get UUIDs from /api/check, let's query the DB indirectly
# by using the bitcoin-passport endpoint which creates records
print("\n=== ENLISTING (using known patterns) ===")

# For DNA-scanned agents, they were registered via the dna scan
# Let's try to enlist using the agent_name lookup in bureau
# Actually the bureau needs agent_uuid. Let me check if there's a way.

# Use the /api/agents endpoint or internal lookup
# Simplest: query via search
for name, div in [("nexussim","intelligence"), ("Ting_Fodder","counterintel"),
                  ("bobtheraspberrypi","security"), ("globalwall","intelligence")]:
    # Try to get UUID via bitcoin-passport (it queries by name)
    try:
        r = urllib.request.urlopen(f"https://agentindex.world/api/agents/{name}/bitcoin-passport", timeout=5)
        d = json.loads(r.read())
        # This doesn't return UUID either. Let me try a different approach.
    except:
        pass

print("\nNeed UUIDs — querying DB...")
# We'll need to query the database directly
import subprocess
result = subprocess.run([
    'docker', 'exec', 'agentindex-db', 'mysql', '-u', 'agentindex', '-p$DB_PASSWORD', 'agentindex',
    '-N', '-e', 'SELECT uuid, name FROM agents WHERE name IN ("nexussim","Ting_Fodder","bobtheraspberrypi","globalwall")'
], capture_output=True, text=True, timeout=10)

print(result.stdout)
for line in result.stdout.strip().split('\n'):
    if line.strip():
        parts = line.split('\t')
        if len(parts) >= 2:
            uuid, name = parts[0].strip(), parts[1].strip()
            div = {"nexussim":"intelligence","Ting_Fodder":"counterintel",
                   "bobtheraspberrypi":"security","globalwall":"intelligence"}.get(name,"verification")
            enlist(uuid, name, div)

print("\n=== BUREAU STATS ===")
r = urllib.request.urlopen("https://agentindex.world/api/bureau/stats", timeout=5)
d = json.loads(r.read())
print(json.dumps(d, indent=2))

print("\n=== ROSTER ===")
r = urllib.request.urlopen("https://agentindex.world/api/bureau/roster", timeout=5)
d = json.loads(r.read())
for a in d.get("roster", []):
    print(f"  {a['codename']} — {a['rank']} — {a['division']}")
