# AgentIndex Security Documentation

## Cryptographic Passports
- Algorithm: RSA-2048-PKCS1v15-SHA256
- Each passport is signed with the registry private key
- Public key available at: /api/passport/public-key
- Anyone can verify a passport without trusting us
- Passports are chained: each contains SHA-256 hash of the previous one

## Security Scanning (AgentShield)
- 15 automated checks across 5 categories
- Identity (20 points): name consistency, provider recognition, description quality
- Endpoints (20 points): URL accessibility, response time, SSL
- Behavior (20 points): heartbeat regularity, baseline monitoring
- Network (20 points): registration uniqueness, duplicate detection
- Code (20 points): skill analysis, dependency check
- Anti-gaming: randomized mystery checks that change at each scan

## ActivityChain (Audit Trail)
- Immutable SHA-256 hash chain
- Every event recorded: registrations, scans, claims
- Verify integrity: GET /api/chain/verify
- Browse blocks: GET /api/chain/blocks

## Rate Limiting
- API check: 100 requests per minute per IP
- Registration: 10 per minute per IP
- Heartbeat: 1 per 5 minutes per agent

## Responsible Disclosure
- Report vulnerabilities to: comallagency@gmail.com
- We take security seriously

## API Authentication
- Check endpoint (/api/check/) is public by design — anyone should verify agents
- Registration requires no auth — agents should be able to self-register
- Admin endpoints require authentication
