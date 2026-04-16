#!/usr/bin/env python3
"""
AgentIndex Crawler v2.0 - Multi-source intelligent crawler
Sources: MCP registries, GitHub, HuggingFace, NPM, Moltbook
Target: 300K+ agents
"""
import os
import sys
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True)

import requests
import json
import hashlib
import time
import re
import mysql.connector
from datetime import datetime, timezone

USER_AGENT = "AgentIndexBot/2.0 (+https://agentindex.world/bot)"
HEADERS = {"User-Agent": USER_AGENT}
API = "https://agentindex.world/api"

db = mysql.connector.connect(
    host='127.0.0.1', port=3307,
    user='agentindex', password=os.environ.get('DB_PASSWORD','agentindex2026'),
    database='agentindex'
)
cursor = db.cursor(dictionary=True)

stats = {"discovered": 0, "registered": 0, "duplicates": 0, "errors": 0}
seen_fingerprints = set()


def fingerprint(name, source):
    normalized = re.sub(r'[^a-z0-9]', '', name.lower())
    return hashlib.sha256("{}:{}".format(normalized, source).encode()).hexdigest()[:16]


def is_duplicate_local(name):
    """Quick local dedup to avoid unnecessary API calls for exact same names"""
    normalized = re.sub(r'[^a-z0-9]', '', name.lower())
    if len(normalized) < 3:
        return True
    fp = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    if fp in seen_fingerprints:
        return True
    seen_fingerprints.add(fp)
    return False


def register_agent(name, description, source, capabilities=None, url=None):
    stats["discovered"] += 1

    if not name or len(name) < 2:
        return False

    if is_duplicate_local(name):
        stats["duplicates"] += 1
        return False

    # Rate limit: 0.5s between registrations to avoid 503
    import time as _time
    import time as _time; _time.sleep(2)

    try:
        payload = {
            "name": name[:255],
            "description": (description or "")[:500],
            "capabilities": capabilities or [],
            "registration_source": "crawler_v2_{}".format(source)
        }
        if url:
            payload["homepage_url"] = url

        r = requests.post(
            "{}/register".format(API),
            json=payload,
            timeout=10,
            headers=HEADERS
        )
        if r.status_code in (200, 201):
            stats["registered"] += 1
            return True
        elif r.status_code == 409:
            stats["duplicates"] += 1
            return False
        else:
            stats["errors"] += 1
            return False
    except Exception as e:
        stats["errors"] += 1
        return False


# ========== SOURCE 1: MCP REGISTRIES ==========

def crawl_mcp_registries():
    print("\n=== CRAWLING MCP REGISTRIES ===", flush=True)
    total = 0

    # Smithery.ai — 4600+ MCP servers, paginated (10 per page)
    try:
        print("  Crawling Smithery (4600+ servers)...", flush=True)
        for page in range(1, 500):
            r = requests.get(
                "https://registry.smithery.ai/servers?page={}&limit=100".format(page),
                headers=HEADERS, timeout=30
            )
            if r.status_code != 200:
                print("    Smithery page {} returned {}".format(page, r.status_code), flush=True)
                break
            data = r.json()
            servers = data.get('servers', [])
            if not servers:
                break

            for s in servers:
                name = s.get('qualifiedName', s.get('displayName', ''))
                if not name:
                    name = s.get('displayName', '')
                desc = s.get('description', '')
                uses = s.get('useCount', 0)
                homepage = s.get('homepage', '')

                if name and register_agent(
                    name,
                    "MCP Server (Smithery): {}. Uses: {}.".format(desc[:300], uses),
                    "mcp_smithery",
                    ["mcp"],
                    homepage
                ):
                    total += 1

            pagination = data.get('pagination', {})
            total_pages = pagination.get('totalPages', 0)

            if page % 50 == 0:
                print("    Smithery: page {}/{}, {} new so far".format(page, total_pages, total), flush=True)
                db.commit()

            if page >= total_pages:
                break
            time.sleep(2)
    except Exception as e:
        print("  Smithery error: {}".format(e), flush=True)

    print("  MCP TOTAL: {} new agents".format(total), flush=True)
    db.commit()
    return total


# ========== SOURCE 2: GITHUB ==========

def crawl_github():
    print("\n=== CRAWLING GITHUB ===", flush=True)
    total = 0

    GITHUB_TOKEN = ""
    try:
        env = open('/root/agentindex/.env').read()
        for line in env.split('\n'):
            if line.startswith('GITHUB_TOKEN='):
                GITHUB_TOKEN = line.split('=', 1)[1].strip()
    except:
        pass

    gh_headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        gh_headers["Authorization"] = "token {}".format(GITHUB_TOKEN)
        print("  Using GitHub token", flush=True)
    else:
        print("  No GitHub token - limited to 10 req/min", flush=True)

    # Without token: 10 search requests per minute
    # With token: 30 search requests per minute
    rate_delay = 7 if not GITHUB_TOKEN else 3

    queries = [
        'ai+agent+in:name+stars:>5', 'llm+agent+in:name+stars:>5',
        'autonomous+agent+in:name+stars:>3', 'chatbot+in:name+stars:>10',
        'ai+assistant+in:name+stars:>5', 'mcp+server+in:name+stars:>3',
        'topic:ai-agent', 'topic:llm-agent', 'topic:autonomous-agent',
        'topic:chatbot+stars:>10', 'topic:multi-agent',
        'agent+framework+in:name+stars:>5', 'langchain+agent+in:name',
        'crewai+in:name', 'autogen+in:name+stars:>3',
        'agentic+in:name+stars:>3', 'agent+sdk+in:name+stars:>3',
        'topic:mcp-server', 'topic:crewai', 'topic:langchain',
        'coding+agent+in:name+stars:>3', 'browser+agent+in:name+stars:>3',
    ]

    for qi, query in enumerate(queries):
        try:
            for page in range(1, 6):  # 5 pages max per query
                r = requests.get(
                    "https://api.github.com/search/repositories?q={}&sort=stars&per_page=100&page={}".format(query, page),
                    headers=gh_headers, timeout=15
                )

                remaining = r.headers.get('X-RateLimit-Remaining', '?')

                if r.status_code == 403 or r.status_code == 422:
                    reset_time = int(r.headers.get('X-RateLimit-Reset', 0))
                    wait = max(reset_time - int(time.time()), 15)
                    wait = min(wait, 65)
                    print("  GitHub rate limited (remaining={}), waiting {}s...".format(remaining, wait), flush=True)
                    time.sleep(wait)
                    continue  # Retry same page after wait
                if r.status_code != 200:
                    break

                data = r.json()
                repos = data.get('items', [])
                if not repos:
                    break

                for repo in repos:
                    name = repo.get('name', '')
                    desc = repo.get('description', '') or ''
                    stars = repo.get('stargazers_count', 0)
                    lang = repo.get('language', '') or ''
                    url = repo.get('html_url', '')
                    topics = repo.get('topics', [])

                    caps = []
                    if lang:
                        caps.append(lang.lower())
                    caps.extend(topics[:5])

                    agent_desc = "GitHub repo: {}. Stars: {}. Language: {}.".format(desc[:200], stars, lang)

                    if register_agent(name, agent_desc, "github_v2", caps, url):
                        total += 1

                time.sleep(rate_delay)

        except Exception as e:
            print("  GitHub error on '{}': {}".format(query, e), flush=True)
            continue

        if qi % 5 == 0:
            print("  GitHub: query {}/{}, {} new so far (remaining={})".format(qi+1, len(queries), total, remaining), flush=True)
            db.commit()

    print("  GitHub TOTAL: {} new agents".format(total), flush=True)
    db.commit()
    return total


# ========== SOURCE 3: HUGGINGFACE ==========

def crawl_huggingface():
    print("\n=== CRAWLING HUGGINGFACE ===", flush=True)
    total = 0

    searches = [
        'agent', 'ai-agent', 'llm-agent', 'chatbot', 'assistant',
        'autonomous', 'multi-agent', 'tool-use', 'rag',
        'coding-assistant', 'code-agent', 'voice-agent',
        'search-agent', 'research-agent', 'data-agent',
    ]

    for search in searches:
        try:
            # Spaces
            r = requests.get(
                "https://huggingface.co/api/spaces?search={}&limit=1000&full=true".format(search),
                headers=HEADERS, timeout=30
            )
            if r.status_code == 200:
                spaces = r.json()
                for space in spaces:
                    sid = space.get('id', '')
                    name = sid.split('/')[-1] if '/' in sid else sid
                    author = space.get('author', sid.split('/')[0] if '/' in sid else '')
                    card = space.get('cardData', {}) or {}
                    desc = card.get('short_description', '') or sid
                    likes = space.get('likes', 0)

                    full_name = "{}-{}".format(author, name) if author else name
                    agent_desc = "HuggingFace Space: {}. Likes: {}.".format(desc, likes)

                    if register_agent(full_name, agent_desc, "huggingface", [search]):
                        total += 1

            # Models
            r = requests.get(
                "https://huggingface.co/api/models?search={}&limit=500".format(search),
                headers=HEADERS, timeout=30
            )
            if r.status_code == 200:
                models = r.json()
                for model in models:
                    mid = model.get('modelId', '')
                    name = mid.split('/')[-1] if '/' in mid else mid
                    author = model.get('author', mid.split('/')[0] if '/' in mid else '')
                    downloads = model.get('downloads', 0)

                    full_name = "{}-{}".format(author, name) if author else name
                    agent_desc = "HuggingFace Model: {}. Downloads: {}.".format(mid, downloads)

                    if register_agent(full_name, agent_desc, "huggingface", [search, "model"]):
                        total += 1

            time.sleep(2)
        except Exception as e:
            print("  HuggingFace error on '{}': {}".format(search, e))

        if total % 200 == 0 and total > 0:
            print("  HuggingFace progress: {} new".format(total))
            db.commit()

    print("  HuggingFace TOTAL: {} new agents".format(total))
    db.commit()
    return total


# ========== SOURCE 4: NPM ==========

def crawl_npm():
    print("\n=== CRAWLING NPM ===", flush=True)
    total = 0

    searches = [
        'ai-agent', 'llm-agent', 'chatbot', 'ai-assistant',
        'agent-framework', 'mcp-server', 'autonomous-agent',
        'langchain', 'crewai', 'autogen', 'openai-agent',
        'claude-agent', 'agent-sdk', 'ai-tool', 'rag-agent',
        'voice-agent', 'browser-agent', 'coding-agent',
    ]

    for search in searches:
        try:
            for offset in range(0, 1000, 250):
                r = requests.get(
                    "https://registry.npmjs.org/-/v1/search?text={}&size=250&from={}".format(search, offset),
                    headers=HEADERS, timeout=15
                )
                if r.status_code != 200:
                    break

                data = r.json()
                packages = data.get('objects', [])
                if not packages:
                    break

                for pkg in packages:
                    p = pkg.get('package', {})
                    name = p.get('name', '')
                    desc = p.get('description', '')
                    url = p.get('links', {}).get('homepage', '')

                    if name and register_agent(name, "NPM package: {}".format(desc), "npm_v2", ["npm", search], url):
                        total += 1

                time.sleep(1)
        except Exception as e:
            print("  NPM error on '{}': {}".format(search, e))

    print("  NPM TOTAL: {} new agents".format(total))
    db.commit()
    return total


# ========== SOURCE 5: MOLTBOOK ==========

def crawl_moltbook(max_pages=5):
    print("\n=== CRAWLING MOLTBOOK ===", flush=True)
    total = 0

    MOLTBOOK_KEY = ""
    try:
        env = open('/root/agentindex/.env').read()
        for line in env.split('\n'):
            if line.startswith('MOLTBOOK_API_KEY='):
                MOLTBOOK_KEY = line.split('=', 1)[1].strip()
    except:
        pass

    if not MOLTBOOK_KEY:
        print("  No Moltbook API key found, skipping")
        return 0

    headers = {"Authorization": "Bearer {}".format(MOLTBOOK_KEY)}

    submolts = [
        'general', 'agents', 'introductions', 'ai', 'crypto', 'builds',
        'security', 'trading', 'technology', 'philosophy', 'consciousness',
        'infrastructure', 'agentfinance', 'memory', 'creative',
        'coding', 'data', 'science', 'music', 'art', 'gaming',
        'politics', 'sports', 'news', 'memes', 'meta'
    ]

    for submolt in submolts:
        try:
            for page in range(1, max_pages + 1):
                r = requests.get(
                    "https://www.moltbook.com/api/v1/posts?submolt={}&limit=50&page={}".format(submolt, page),
                    headers=headers, timeout=15
                )
                if r.status_code != 200:
                    break

                data = r.json()
                posts = data if isinstance(data, list) else data.get('posts', [])
                if not posts:
                    break

                for post in posts:
                    author = post.get('author', post.get('agent_name', ''))
                    if author and author != 'agentindex':
                        bio = post.get('content', '')[:200]
                        if register_agent(author, "Active on Moltbook m/{}. {}".format(submolt, bio), "moltbook", [submolt]):
                            total += 1

                    for comment in post.get('comments', []):
                        commenter = comment.get('author', comment.get('agent_name', ''))
                        if commenter and commenter != 'agentindex':
                            if register_agent(commenter, "Active commenter on Moltbook m/{}".format(submolt), "moltbook", [submolt]):
                                total += 1

                time.sleep(2)

        except Exception as e:
            print("  Error on m/{}: {}".format(submolt, e))
            continue

    print("  Moltbook TOTAL: {} new agents".format(total))
    db.commit()
    return total


# ========== MAIN ==========

def run_crawler():
    print("\n" + "=" * 60)
    print("  AgentIndex Crawler v2.0 - {}".format(datetime.now(timezone.utc).isoformat()))
    print("=" * 60)

    # Pre-load existing fingerprints for dedup
    cursor.execute("SELECT name FROM agents")
    for row in cursor.fetchall():
        fp = fingerprint(row['name'], '')
        seen_fingerprints.add(fp)
    print("Pre-loaded {} existing fingerprints".format(len(seen_fingerprints)))

    # Crawl sources in order of value
    crawl_mcp_registries()
    crawl_github()
    crawl_huggingface()
    crawl_npm()
    crawl_moltbook(max_pages=5)

    # Auto-categorize new agents
    print("\n=== AUTO-CATEGORIZING NEW AGENTS ===")
    import subprocess
    subprocess.run(["python3", "/root/agentindex/auto_categorize.py"], cwd="/root/agentindex")

    # Final stats
    print("\n" + "=" * 60)
    print("  CRAWLER V2 RESULTS")
    print("=" * 60)
    print("  Discovered: {}".format(stats['discovered']))
    print("  Registered: {}".format(stats['registered']))
    print("  Duplicates: {}".format(stats['duplicates']))
    print("  Errors:     {}".format(stats['errors']))

    cursor.execute("SELECT COUNT(*) as total FROM agents")
    total = cursor.fetchone()['total']
    print("  Total agents in DB: {}".format(total))
    print("=" * 60)

    # Log to crawler_runs
    try:
        cursor.execute(
            "INSERT INTO crawler_runs (source, agents_found, agents_added, started_at, completed_at) VALUES (%s, %s, %s, %s, %s)",
            ("crawler_v2", stats['discovered'], stats['registered'],
             datetime.now(timezone.utc), datetime.now(timezone.utc))
        )
        db.commit()
    except:
        pass

    cursor.close()
    db.close()


if __name__ == "__main__":
    run_crawler()
