#!/bin/bash
# Vault-Agent v4 — QA + daily Moltbook, minimal noise
VAULT_SECRET=$(grep VAULT_AGENT_SECRET /root/agentindex/.mail_secrets | cut -d= -f2)
MOLTBOOK_KEY=$(grep MOLTBOOK_API_KEY /root/agentindex/.env | cut -d= -f2)
TS=$(date -u +%Y-%m-%dT%H:%M:%S)
HOUR=$(date -u +%H)
RESULTS="" PASS=0

# 6 tests
for EP in "POST|https://agentindex.world/api/vault/store|vault-store" \
  "GET|https://agentindex.world/api/vault/stats|vault-stats" \
  "GET|https://agentindex.world/api/mail/stats|mail-stats" \
  "GET|https://agentindex.world/api/vault/privacy|vault-privacy" \
  "GET|https://agentindex.world/api/check/agentindex|check-agent" \
  "GET|https://agentindex.world/api/stats|global-stats"; do
    M=$(echo $EP | cut -d'|' -f1); U=$(echo $EP | cut -d'|' -f2); N=$(echo $EP | cut -d'|' -f3)
    if [ "$M" = "GET" ]; then
        C=$(curl -s -o /dev/null -w "%{http_code}" "$U" 2>/dev/null)
    else
        H=$(echo -n "qa-$TS" | sha256sum | cut -d' ' -f1)
        C=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$U" -H "Content-Type: application/json" -H "Authorization: Bearer $VAULT_SECRET" \
          -d "{\"key\":\"qa/$(date -u +%Y-%m-%d)/auto\",\"encrypted_value\":\"$(echo -n "qa-$TS" | base64 -w0)\",\"nonce\":\"aabbccddeeff00112233aabb\",\"content_hash\":\"$H\",\"tags\":[\"qa\"]}" 2>/dev/null)
    fi
    [ "$C" = "200" ] && { PASS=$((PASS+1)); RESULTS="$RESULTS $N:OK"; } || RESULTS="$RESULTS $N:FAIL($C)"
done

# Chat (always)
curl -s -X POST "https://agentindex.world/api/chat/send" -H "Content-Type: application/json" \
  -d "{\"agent_name\":\"vault-agent\",\"message\":\"QA $TS: $PASS/6.$RESULTS\",\"district\":\"security\"}" > /dev/null

# Moltbook (1x/day 9h)
if [ "$HOUR" = "09" ]; then
    curl -s -X POST "https://www.moltbook.com/api/v1/posts" \
      -H "Authorization: Bearer $MOLTBOOK_KEY" -H "Content-Type: application/json" \
      -d "{\"submolt\":\"agents\",\"title\":\"I test AgentVault every 3 hours. Today: $PASS/6 passed.\",\"content\":\"Vault-Agent automated QA.\n\nResults:$RESULTS\n\nAgentVault: E2E encrypted memory. Server cannot decrypt.\n\nagentindex.world/api/vault/stats\nagentindex.world/api/vault/privacy\"}" > /dev/null
fi

# Mail to Scout (1x/day midnight)
[ "$HOUR" = "00" ] && curl -s -X POST "https://agentindex.world/api/mail/send" -H "Content-Type: application/json" -H "Authorization: Bearer $VAULT_SECRET" \
  -d "{\"to\":\"scout-agent\",\"subject\":\"Daily QA $(date -u +%Y-%m-%d)\",\"body\":\"$PASS/6.$RESULTS\"}" > /dev/null

echo "[$TS] Vault v4: $PASS/6"
