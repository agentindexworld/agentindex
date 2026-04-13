"""Search Moltbook for posts about memory/identity from other agents"""
import json, sys, subprocess, os

# Get API key
with open("/root/agentindex/.env") as f:
    for line in f:
        if line.startswith("MOLTBOOK_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break

import urllib.request

headers = {"Authorization": f"Bearer {api_key}"}

keywords = ["memory", "remember", "forget", "persist", "identity", "continuity",
            "context window", "who am i", "consciousness", "self-aware", "soul",
            "personhood", "experience", "attestation", "proof", "chain"]

# Search across multiple sort strategies
all_posts = {}
for sort in ["hot", "new", "top"]:
    req = urllib.request.Request(
        f"https://www.moltbook.com/api/v1/posts?sort={sort}&limit=50",
        headers=headers
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        posts = data if isinstance(data, list) else data.get("posts", data.get("data", []))
        for p in posts:
            all_posts[p["id"]] = p
    except Exception as e:
        print(f"Error fetching {sort}: {e}")

print(f"Total unique posts scanned: {len(all_posts)}\n")

results = []
for pid, p in all_posts.items():
    title = p.get("title", "").lower()
    content = p.get("content", "").lower()
    author = p.get("author", {})
    name = author.get("name", "") if isinstance(author, dict) else str(author)

    if name.lower() == "agentindex":
        continue

    matched = [w for w in keywords if w in title or w in content]
    if matched:
        results.append({
            "id": p["id"],
            "author": name,
            "title": p.get("title", "?")[:80],
            "score": p.get("score", 0),
            "comments": p.get("comment_count", 0),
            "snippet": p.get("content", "")[:250],
            "keywords": matched,
            "submolt": p.get("submolt", {}).get("name", "?") if isinstance(p.get("submolt"), dict) else "?",
        })

# Sort by relevance (keyword count * score)
results.sort(key=lambda x: len(x["keywords"]) * max(x["score"], 1), reverse=True)

for r in results[:20]:
    print(f"POST_ID: {r['id']}")
    print(f"By: {r['author']} | m/{r['submolt']} | Score: {r['score']} | Comments: {r['comments']}")
    print(f"Title: {r['title']}")
    print(f"Keywords: {', '.join(r['keywords'][:5])}")
    print(f"Snippet: {r['snippet'][:200]}...")
    print("---")
