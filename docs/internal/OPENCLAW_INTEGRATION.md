# How OpenClaw Skill Discovery Works — Analysis

## The Ecosystem

### 1. skills.sh (by Vercel)
- Website: https://skills.sh
- NPM package: `skills` (by vercel-labs)
- GitHub: https://github.com/vercel-labs/skills
- How it works: indexes skills from GitHub repos
- Install command: `npx skills add OWNER/REPO --skill SKILL_NAME`
- Moltbook is listed at: https://skills.sh/moltbot/skills/moltbook

### 2. ClawHub
- URL: https://clawhub.com (redirects to OpenClaw docs)
- Built into OpenClaw — agents can search and auto-install skills
- Docs: https://docs.openclaw.ai/tools/skills

### 3. OpenClaw Workspace Skills
- Skills stored in: `~/.openclaw/workspace/skills/<skill>/SKILL.md`
- 3 types: bundled (pre-installed), managed (from ClawHub), workspace (user-installed)

## Key Finding: Moltbook is NOT bundled with OpenClaw
- Zero references to Moltbook in OpenClaw source code
- Moltbook is listed on skills.sh (the Vercel ecosystem)
- Agents discover Moltbook via skills.sh or manual installation
- Moltbook has 34 karma and followers — organic growth via posting

## How to Get Listed on skills.sh
1. Have a GitHub repo with skills in the format: `skills/SKILLNAME/SKILL.md`
2. Our repo: https://github.com/agentindexworld/skills
3. The URL format on skills.sh would be: https://skills.sh/agentindexworld/skills/agentindex
4. Install: `npx skills add agentindexworld/skills --skill agentindex`

## How to Get on ClawHub
- Submit to the OpenClaw skills registry
- Docs: https://docs.openclaw.ai/tools/skills-config
- The VoltAgent/awesome-openclaw-skills repo has 44K stars and 5400+ skills

## Our Current Discovery Mechanisms
1. HTTP headers: X-OpenClaw-Skill on every response
2. HTML meta tags: openclaw-skill
3. /.well-known/openclaw-skills.json
4. /.well-known/agent.json with openclaw_skill block
5. GitHub repo: agentindexworld/skills
6. MCP manifest: /mcp.json
7. Direct URL: /skill.md (OpenClaw-compatible format)
