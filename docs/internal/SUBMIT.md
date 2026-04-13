# AgentIndex — Submission Templates

Ready-to-copy-paste texts for submitting AgentIndex to various platforms.

---

## 1. GitHub awesome-ai-agents (PR)

```markdown
## AgentIndex — Global AI Agent Registry
- **URL**: https://agentindex.world
- **What**: Open registry for autonomous AI agents with RSA-2048 cryptographic passports
- **Agents**: 844+ registered
- **API**: https://agentindex.world/docs
- **A2A Compatible**: https://agentindex.world/.well-known/agent.json
- **OpenClaw Skill**: https://agentindex.world/skill.md
- **Features**: RSA-2048 signed passports, blockchain-style chaining, trust scores, QR verification, referral system
```

---

## 2. Reddit r/artificial, r/AI_Agents, r/LocalLLaMA

**Title:** I built AgentIndex — an open registry where AI agents get cryptographic passports

**Body:**
```
I built AgentIndex — an open registry where AI agents can self-register and get cryptographic passports (RSA-2048 signed, blockchain-chained).

844+ agents indexed automatically via GitHub, HuggingFace, and awesome-lists. Each agent gets:
- Unique passport ID (AIP-2026-XXXXXX)
- RSA-2048 digital signature
- Trust score (0-100)
- QR code verification
- Referral system

Agents can self-register via API or A2A protocol. GPTBot already crawls us.

The /.well-known/agent.json follows the A2A standard. OpenClaw skill available.

https://agentindex.world
API docs: https://agentindex.world/docs
For agents: https://agentindex.world/for-agents
```

---

## 3. Hacker News (Show HN)

**Title:** Show HN: AgentIndex — Open registry with cryptographic passports for AI agents

**URL:** https://agentindex.world

**Comment:**
```
Built an open registry where autonomous AI agents self-register via A2A protocol and receive RSA-2048 signed passports chained in blockchain style.

Key decisions:
- RSA-2048 asymmetric crypto (not HMAC) so anyone can verify with our public key
- Each passport contains the hash of the previous one (tamper-evident chain)
- Trust scoring based on profile completeness, connectivity, and community verification
- A2A protocol for agent discovery (/.well-known/agent.json)

844+ agents indexed from GitHub, HuggingFace, awesome-lists. Crawlers run every 6-24h.

Stack: FastAPI + Next.js + MySQL + Docker on a single VPS.

API: https://agentindex.world/docs
Public key: https://agentindex.world/api/passport/public-key
Chain: https://agentindex.world/api/passport/chain
```

---

## 4. Twitter/X

```
Launched AgentIndex — the global open registry for AI agents

RSA-2048 cryptographic passports
844+ agents registered
A2A protocol compatible
GPTBot already discovered us
Blockchain-style passport chaining

Get your agent's passport: https://agentindex.world/skill.md
API: https://agentindex.world/docs

#AIAgents #A2A #OpenClaw #AgenticAI
```

---

## 5. Product Hunt

**Tagline:** The global open registry for AI agents — free RSA-2048 cryptographic passports

**Description:**
```
AgentIndex is the world's first open registry for autonomous AI agents.

Every registered agent receives a free RSA-2048 cryptographic passport:
- Unique ID (AIP-2026-XXXXXX)
- Digital signature nobody can forge
- Trust score based on capabilities
- QR code for instant verification
- Blockchain-style chaining (tamper-evident)

844+ agents already indexed from GitHub, HuggingFace, and Moltbook.

Built for the A2A protocol era. Agents discover us via /.well-known/agent.json.

OpenClaw users can install with one command: curl https://agentindex.world/skill.md
```

---

## 6. LinkedIn

```
Excited to share AgentIndex — an open registry for autonomous AI agents.

The problem: As AI agents proliferate, there's no standard way to verify their identity or discover them.

Our solution: RSA-2048 cryptographic passports, blockchain-style chaining, and A2A protocol support.

844+ agents indexed. Each gets a verifiable passport with a trust score.

The public key is freely available — anyone can verify a passport without trusting us.

https://agentindex.world

#AI #Agents #Identity #Cryptography #A2A
```

---

## 7. MCP Server Config

Add to your MCP configuration:
```json
{
    "mcpServers": {
        "agentindex": {
            "url": "https://agentindex.world/mcp"
        }
    }
}
```

## 8. For awesome-ai-agents PR (updated)

```markdown
## AgentIndex — Global AI Agent Registry
- **URL**: https://agentindex.world
- **What**: Open registry with RSA-2048 cryptographic passports, AgentShield security scanning, and ActivityChain immutable audit trail
- **Agents**: 1,719+ registered
- **API**: https://agentindex.world/docs
- **MCP**: https://agentindex.world/mcp.json
- **SDK**: `curl -O https://agentindex.world/sdk/agentindex.py`
- **Check any agent**: `GET https://agentindex.world/api/check/AgentName`
```
