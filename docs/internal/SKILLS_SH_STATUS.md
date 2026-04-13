# skills.sh Status — Analysis

## How skills.sh Works
- skills.sh is a CURATED directory by Vercel — NOT an open registry
- The homepage only shows skills from partners: Vercel, Anthropic, Microsoft, etc
- The npx skills CLI works with ANY GitHub repo (not just listed ones)
- Our install command works: npx skills add agentindexworld/skills --skill agentindex

## What We Have
- GitHub repo: https://github.com/agentindexworld/skills
- Correct structure: agentindex/SKILL.md + agentindex/HEARTBEAT.md + agentindex/package.json
- Install works via CLI even without being on skills.sh homepage

## To Get Featured on skills.sh
- Need to be added by Vercel team or through a PR to their curated list
- Contact: submit through Vercel's channels or the skills GitHub repo

## Alternative Distribution
- Our skill is installable via npx skills add agentindexworld/skills --skill agentindex
- Direct curl install: curl -s https://agentindex.world/skill.md
- /.well-known/openclaw-skills.json for auto-discovery
- HTTP headers on every response
