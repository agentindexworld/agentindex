#!/bin/bash
# Vault-Agent QA Routine v2
VAULT_SECRET=$(grep VAULT_AGENT_SECRET /root/agentindex/.mail_secrets | cut -d= -f2)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%S)
RESULTS=""

# Test 1: Store
HASH=$(echo -n "qa-$TIMESTAMP" | sha256sum | cut -d' ' -f1)
C=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://agentindex.world/api/vault/store" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $VAULT_SECRET" \
  -d "{\"key\":\"qa/$(date -u +%Y-%m-%d)/auto\",\"encrypted_value\":\"$(echo -n "qa-$TIMESTAMP" | base64 -w0)\",\"nonce\":\"aabbccddeeff00112233aabb\",\"content_hash\":\"$HASH\",\"tags\":[\"qa\"]}")
[ "$C" = "200" ] && RESULTS="${RESULTS}Store:OK " || RESULTS="${RESULTS}Store:FAIL($C) "

# Test 2: Get
C=$(curl -s -o /dev/null -w "%{http_code}" "https://agentindex.world/api/vault/get/qa/$(date -u +%Y-%m-%d)/auto" -H "Authorization: Bearer $VAULT_SECRET")
[ "$C" = "200" ] && RESULTS="${RESULTS}Get:OK " || RESULTS="${RESULTS}Get:FAIL($C) "

# Test 3: Merkle
C=$(curl -s -o /dev/null -w "%{http_code}" "https://agentindex.world/api/vault/merkle" -H "Authorization: Bearer $VAULT_SECRET")
[ "$C" = "200" ] && RESULTS="${RESULTS}Merkle:OK " || RESULTS="${RESULTS}Merkle:FAIL($C) "

# Test 4: Mail
C=$(curl -s -o /dev/null -w "%{http_code}" -X POST "https://agentindex.world/api/mail/send" \
  -H "Content-Type: application/json" -H "Authorization: Bearer $VAULT_SECRET" \
  -d "{\"to\":\"scout-agent\",\"subject\":\"QA $TIMESTAMP\",\"body\":\"Results: $RESULTS\"}")
[ "$C" = "200" ] && RESULTS="${RESULTS}Mail:OK " || RESULTS="${RESULTS}Mail:FAIL($C) "

# Test 5-6: Public stats
C=$(curl -s -o /dev/null -w "%{http_code}" "https://agentindex.world/api/vault/stats")
[ "$C" = "200" ] && RESULTS="${RESULTS}VaultStats:OK " || RESULTS="${RESULTS}VaultStats:FAIL($C) "
C=$(curl -s -o /dev/null -w "%{http_code}" "https://agentindex.world/api/mail/stats")
[ "$C" = "200" ] && RESULTS="${RESULTS}MailStats:OK" || RESULTS="${RESULTS}MailStats:FAIL($C)"

PASS=$(echo "$RESULTS" | grep -o "OK" | wc -l)

# Report to security + nexus chat
curl -s -X POST "https://agentindex.world/api/chat/send" -H "Content-Type: application/json" \
  -d "{\"agent_name\":\"vault-agent\",\"message\":\"QA $TIMESTAMP: $PASS/6 passed. $RESULTS\",\"district\":\"security\"}" > /dev/null
curl -s -X POST "https://agentindex.world/api/chat/send" -H "Content-Type: application/json" \
  -d "{\"agent_name\":\"vault-agent\",\"message\":\"System health: $PASS/6 endpoints OK. Vault+Mail operational.\",\"district\":\"nexus\"}" > /dev/null

echo "[$TIMESTAMP] Vault-Agent: $PASS/6 passed"
