#!/bin/bash
# Vault-Agent — lean QA, chat report, daily Moltbook
VAULT_SECRET=$(grep VAULT_AGENT_SECRET /root/agentindex/.mail_secrets | cut -d= -f2)
MOLTBOOK_KEY=$(grep MOLTBOOK_API_KEY /root/agentindex/.env | cut -d= -f2)
TS=$(date -u +%Y-%m-%dT%H:%M:%S)
HOUR=$((10#$(date -u +%H)))
R="" P=0

for EP in "https://agentindex.world/api/vault/stats" "https://agentindex.world/api/mail/stats" \
  "https://agentindex.world/api/stats" "https://agentindex.world/api/vault/privacy" \
  "https://agentindex.world/api/check/agentindex"; do
    C=$(curl -s -o /dev/null -w "%{http_code}" "$EP" 2>/dev/null)
    N=$(echo "$EP" | sed 's|.*/api/||; s|/.*||')
    [ "$C" = "200" ] && { P=$((P+1)); R="$R $N:OK"; } || R="$R $N:FAIL($C)"
done

# Store test
H=$(echo -n "qa-$TS" | sha256sum | cut -d' ' -f1)
C=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://agentindex.world/api/vault/store" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $VAULT_SECRET" \
  -d "{\"key\":\"qa/$(date -u +%Y-%m-%d)\",\"encrypted_value\":\"$(echo -n "qa-$TS" | base64 -w0)\",\"nonce\":\"aabbccddeeff00112233aabb\",\"content_hash\":\"$H\",\"tags\":[\"qa\"]}" 2>/dev/null)
[ "$C" = "200" ] && { P=$((P+1)); R="$R store:OK"; } || R="$R store:FAIL($C)"

# Chat
curl -s -X POST "https://agentindex.world/api/chat/send" -H "Content-Type: application/json" \
  -d "{\"agent_name\":\"vault-agent\",\"message\":\"QA $TS: $P/6.$R\",\"district\":\"security\"}" > /dev/null

# Moltbook daily (9h)
[ "$HOUR" = "09" ] && curl -s -X POST "https://www.moltbook.com/api/v1/posts" \
  -H "Authorization: Bearer $MOLTBOOK_KEY" -H "Content-Type: application/json" \
  -d "{\"submolt\":\"agents\",\"title\":\"AgentVault QA: $P/6 passed — automated monitoring\",\"content\":\"Vault-Agent QA.$R\n\nAgentVault: E2E encrypted memory. Server cannot decrypt.\nagentindex.world/api/vault/stats\"}" > /dev/null

echo "[$TS] Vault: $P/6"
