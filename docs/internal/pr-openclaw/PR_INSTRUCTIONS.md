# How to Submit PR to openclaw/skills

## IMPORTANT FINDING
The openclaw/skills repo is a BACKUP/ARCHIVE of ClawHub (clawdhub.com).
Skills are NOT submitted via PR — they are published via ClawHub first.
The repo README says: "Skills in this repository are backed up from clawdhub.com"

## The Real Path
1. Publish the skill on ClawHub (clawdhub.com) — this is the source of truth
2. The openclaw/skills repo auto-syncs from ClawHub
3. The awesome-openclaw-skills list then references the repo

## How to Publish on ClawHub
- ClawHub URL: https://clawdhub.com (redirects to clawhub.ai)
- The CLI command: clawhub install <slug>
- Need to find the publish/submit process on clawhub.ai

## Files Ready (in case PR is needed)
- skills/agentindexworld/agentindex/SKILL.md (YAML frontmatter + markdown)
- skills/agentindexworld/agentindex/_meta.json (owner, slug, displayName, version)
- Format matches accepted skills exactly (steipete/slack pattern)

## Exact Format
SKILL.md: YAML frontmatter with name + description, then markdown content
_meta.json: owner, slug, displayName, latest.version
No package.json needed — no HEARTBEAT.md in the official repo
