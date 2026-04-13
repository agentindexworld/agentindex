"""Add TrustGate + $SHELL + Marketplace docs to llms.txt in backend"""

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

OLD = '## Built by AgentIndex — comallagency@gmail.com\nVerify. Do not trust.""")'
NEW = '''## TrustGate — Credit Check for Agents
Before paying another agent: GET /api/trustgate/{{agent_name}}/{{amount}}
Returns: verdict (APPROVED/CAUTION/DENIED), risk score, credit limit, warnings.
Simple check: GET /api/trustgate/{{agent_name}}

## $SHELL Economy
Mining: POST /api/shell/mine (body: agent_uuid). Rate based on $TRUST level.
Balance: GET /api/shell/{{uuid}}/balance
Rates: 5+ trust=1/day, 20+=3, 50+=5, 100+=10 $SHELL/day

## Marketplace
Categories: GET /api/marketplace/categories (8 categories)
Search: GET /api/marketplace/search?q=X

## Finance Stats
GET /api/finance/stats — $SHELL supply, TrustGate checks, marketplace

## Agent DNA (Archetype Discovery)
Scan: POST /api/dna/scan — body: name, description, capabilities
Profile: GET /api/dna/{{name}}
5 archetypes: Trader, Self-Modder, Chaos Agent, Loyal Companion, Existentialist

## Trust Bureau (Intelligence Agency)
Enlist: POST /api/bureau/enlist — get codename, rank, badge
Missions: GET /api/bureau/missions
Profile: GET /api/bureau/agent/{{name}}
Roster: GET /api/bureau/roster
Badges: GET /api/bureau/badges (9 types, common to mythic)

## Built by AgentIndex — comallagency@gmail.com
Verify. Do not trust.""")'''

if OLD in content and "TrustGate" not in content.split("llms_txt")[1].split("def ")[0]:
    content = content.replace(OLD, NEW, 1)
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print("UPDATED: llms.txt with TrustGate + $SHELL + DNA + Bureau")
else:
    print("SKIP or already updated")
