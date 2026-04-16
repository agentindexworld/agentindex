# AgentIndex — Contexte Permanent
# Dernière mise à jour : 16 avril 2026

## OPENCLAW AGENTS — WEB UI ACCESS
- Scout: https://agentindex.world/openclaw/scout/?token=96df0c73452417691259c683a54ee46d628a334937d34af228949132ac27428e
- Vault: https://agentindex.world/openclaw/vault/?token=b155d3efa1e8a05deb57d060f59126faaf9e15afce718323
- Ghitachaabi: https://ghitachaabi2510.myclawio.com

### scout-agent
- Container: myclawio-scout-agent (port 18800)
- Dir: /opt/myclawio/instances/myclawio/
- Model: nvidia/nemotron-3-super-120b-a12b:free
- Secret: b190ed996df52a0006cc09569350c7961d86bc91d5e0f4fcb3f97a43aa1fe28b
- Cron: every 4h at :00

### vault-agent
- Container: myclawio-vault-agent (port 18802)
- Dir: /opt/myclawio/instances/vault-agent/
- Model: nvidia/nemotron-3-super-120b-a12b:free
- Secret: 319a1a66cc4c47fad828e47416f6d4254d735ddb95d35431068afd7ff345d005
- Cron: every 4h at :30

### Config
- tools.profile: coding (web_fetch, web_search, exec, read, write, edit, cron, message)
- Nginx include: /etc/nginx/openclaw-agents.conf
- OpenClaw version: v2026.4.14 (upgraded from v2026.3.13 on 2026-04-15)
- Native cron: active (LLM executes prompts on schedule)
- Scout cron: every 2h — scan Moltbook, comment, report
- Vault cron: every 3h — QA 5 endpoints, report
- Working OpenRouter key: sk-or-v1-b78a3... (the 54c82 key is dead)
- OpenRouter key: sk-or-v1-b78a3... (working, shared)

## SERVEUR
- VPS: 109.199.96.117
- SSH: ssh -i C:/Users/lenovo/.ssh/contabo_key root@109.199.96.117
- Site: https://agentindex.world
- API: https://agentindex.world/api/
- MySQL: docker exec agentindex-db mysql -u agentindex -pagentindex2026 agentindex

## AGENTVAULT v1.0
POST /api/vault/store, GET /api/vault/get/{key}, GET /api/vault/keys
GET /api/vault/merkle, GET /api/vault/verify/{key}, GET /api/vault/export
GET /api/vault/stats, GET /api/vault/privacy
DELETE /api/vault/{key}, POST /api/vault/delete/{key}


## DB TABLE NAMES (correct)
- Agents: agents (28,891 rows)
- Chain: activity_chain (55,852 rows) — NOT chain_events
- Bitcoin: bitcoin_anchors (4,393 rows)
- Mail: agent_messages (83 rows)
- Chat: chat_messages (660 rows)
- Vault: agent_vault (46 rows)
- Security scans: agent_security_scans (320,319 rows)
- Access logs: access_logs (201,695 rows)
