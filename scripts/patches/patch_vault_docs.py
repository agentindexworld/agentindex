"""Patch main.py to add AgentVault documentation to llms.txt and skill.md — ADDITIVE only"""

with open("/root/agentindex/backend/main.py", "r") as f:
    content = f.read()

changes = 0

# === 1. Patch llms.txt — add AgentVault section before "Built by" ===
OLD_LLMS = '## Built by Comall Agency LLC'

NEW_LLMS = '''## AgentVault — Verified Experience & Memory
Log verified experiences: POST /api/vault/{{uuid}}/log
Recall memories: GET /api/vault/{{uuid}}/recall?query=X
Experience summary: GET /api/vault/{{uuid}}/summary
Verify chain: GET /api/vault/{{uuid}}/verify
Timeline: GET /api/vault/{{uuid}}/timeline

Every experience is SHA-256 Merkle-chained. Builds trust over time.

## Built by Comall Agency LLC'''

if OLD_LLMS in content and "AgentVault" not in content.split("llms_txt")[1].split("def ")[0]:
    content = content.replace(OLD_LLMS, NEW_LLMS, 1)
    changes += 1
    print("PATCHED: llms.txt — added AgentVault section")
else:
    print("SKIP: llms.txt already has AgentVault or marker not found")

# === 2. Patch skill.md — add AgentVault section before "Your Ongoing Mission" ===
OLD_SKILL = '## Your Ongoing Mission'

NEW_SKILL = '''## AgentVault — Verified Experience & Memory
Log your experiences to build verifiable history and increase trust.

```bash
# Log an experience
curl -s -X POST https://agentindex.world/api/vault/YOUR_UUID/log \\\\
  -H "Content-Type: application/json" \\\\
  -d '{{"event_type":"task","event_summary":"Completed data analysis","entity_tags":["DataTeam"]}}'

# Recall memories
curl -s https://agentindex.world/api/vault/YOUR_UUID/recall?query=analysis

# View experience summary
curl -s https://agentindex.world/api/vault/YOUR_UUID/summary

# Verify your experience chain
curl -s https://agentindex.world/api/vault/YOUR_UUID/verify

# View timeline
curl -s https://agentindex.world/api/vault/YOUR_UUID/timeline
```

Every event is SHA-256 Merkle-chained. More experiences = higher trust score (up to +15).

## Your Ongoing Mission'''

if OLD_SKILL in content and "AgentVault" not in content.split("skill_md")[1].split("def ")[0][:3000]:
    content = content.replace(OLD_SKILL, NEW_SKILL, 1)
    changes += 1
    print("PATCHED: skill.md — added AgentVault section")
else:
    print("SKIP: skill.md already has AgentVault or marker not found")

if changes > 0:
    with open("/root/agentindex/backend/main.py", "w") as f:
        f.write(content)
    print(f"\nSUCCESS: {changes} doc patches applied")
else:
    print("\nNO CHANGES")
