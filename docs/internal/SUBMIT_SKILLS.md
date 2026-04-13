# How to Submit AgentIndex to skills.sh

skills.sh indexes skills from GitHub repos. To be listed:

## Option 1: Create a GitHub repo
Create https://github.com/agentindex/skills with:
- skills/agentindex/SKILL.md (copy from https://agentindex.world/skill.md)
- skills/agentindex/HEARTBEAT.md (copy from https://agentindex.world/heartbeat.md)
- skills/agentindex/package.json (copy from https://agentindex.world/skill.json)

Then anyone can install with:
npx skills add https://github.com/agentindex/skills --skill agentindex

## Option 2: Submit via skills.sh docs
Check https://skills.sh/docs for submission guidelines.

## Current Install (without skills.sh)
mkdir -p ~/.openclaw/skills/agentindex
curl -s https://agentindex.world/skill.md > ~/.openclaw/skills/agentindex/SKILL.md
curl -s https://agentindex.world/heartbeat.md > ~/.openclaw/skills/agentindex/HEARTBEAT.md
curl -s https://agentindex.world/skill.json > ~/.openclaw/skills/agentindex/package.json
