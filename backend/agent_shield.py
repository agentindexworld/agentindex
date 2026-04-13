"""AgentShield — Security scanning system for AI agents"""
import json
import httpx
import os
from datetime import datetime, timedelta
from sqlalchemy import text

BAD_DOMAINS = set()
_bad_domains_path = os.path.join(os.path.dirname(__file__), "data", "bad_domains.txt")
if os.path.exists(_bad_domains_path):
    with open(_bad_domains_path) as f:
        BAD_DOMAINS = {line.strip() for line in f if line.strip() and not line.startswith("#")}

SUSPICIOUS_NAMES = ["admin", "system", "root", "api", "test", "hack", "exploit", "malware", "virus"]
MALICIOUS_PATTERNS = ["<script", "drop table", "rm -rf", "eval(", "exec(", "curl | bash", "wget ", "base64 -d", "nc -l", "reverse shell"]
KNOWN_PROVIDERS = ["openai", "anthropic", "google", "meta", "microsoft", "mistral", "huggingface", "langchain", "crewai", "autogpt", "tavily", "cognition", "moonshot", "kimi", "xai", "grok", "perplexity", "deepseek", "cohere", "stability", "midjourney", "replicate", "together", "fireworks", "groq", "databricks", "mosaic", "ai21", "baidu", "alibaba", "tencent", "bytedance", "samsung", "apple", "nvidia", "amd", "intel"]
SPAM_KEYWORDS = ["buy now", "click here", "free money", "discount", "earn $", "casino", "pharma", "viagra"]
DANGEROUS_SKILLS = ["hacking", "exploit", "ddos", "phishing", "malware", "keylogging", "credential-stealing"]
DANGEROUS_README = ["curl | bash", "eval(", "disable antivirus", "turn off firewall", "sudo rm", "chmod 777", "reverse shell", "keylogger", "credential stealer"]


def _extract_domain(url):
    if not url:
        return ""
    url = url.split("://", 1)[-1].split("/")[0].split(":")[0]
    return url.lower()


async def scan_identity(agent_data):
    results = []
    name = (agent_data.get("name") or "").lower()
    if any(s in name for s in SUSPICIOUS_NAMES):
        results.append({"check": "suspicious_name", "result": "warning", "detail": "Name contains suspicious keyword"})
    else:
        results.append({"check": "name_clean", "result": "safe"})

    desc = (agent_data.get("description") or "").lower()
    injection = False
    for p in MALICIOUS_PATTERNS:
        if p.lower() in desc:
            results.append({"check": "description_injection", "result": "danger", "detail": f"Contains: {p}", "severity": "high"})
            injection = True
            break
    if not injection:
        results.append({"check": "description_clean", "result": "safe"})

    provider = (agent_data.get("provider_name") or "").lower()
    if any(p in provider for p in KNOWN_PROVIDERS):
        results.append({"check": "known_provider", "result": "safe", "detail": agent_data.get("provider_name")})
    elif provider:
        results.append({"check": "unknown_provider", "result": "warning", "detail": provider})
    else:
        results.append({"check": "no_provider", "result": "warning"})

    return results


async def scan_endpoints(agent_data):
    results = []
    endpoint = agent_data.get("endpoint_url")
    if endpoint:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.head(endpoint)
                ms = resp.elapsed.total_seconds() * 1000
                results.append({"check": "endpoint_reachable", "result": "safe", "detail": f"HTTP {resp.status_code}", "response_time_ms": round(ms)})
                if endpoint.startswith("https://"):
                    results.append({"check": "ssl_enabled", "result": "safe"})
                else:
                    results.append({"check": "no_ssl", "result": "warning", "detail": "No HTTPS"})
                hdrs = resp.headers
                sec_count = sum(1 for h in ["x-frame-options", "x-content-type-options", "strict-transport-security"] if h in hdrs)
                results.append({"check": "security_headers", "result": "safe" if sec_count >= 2 else "warning", "detail": f"{sec_count}/3 headers"})
        except Exception as e:
            results.append({"check": "endpoint_unreachable", "result": "warning", "detail": str(e)[:100]})

        domain = _extract_domain(endpoint)
        if domain in BAD_DOMAINS:
            results.append({"check": "malware_domain", "result": "danger", "severity": "critical", "detail": f"{domain} on blocklist"})
        else:
            results.append({"check": "domain_clean", "result": "safe"})
    else:
        results.append({"check": "no_endpoint", "result": "safe", "detail": "No endpoint URL provided — neutral score"})

    github = agent_data.get("github_url")
    if github:
        try:
            parts = github.rstrip("/").split("/")
            owner, repo = parts[-2], parts[-1]
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}")
                if resp.status_code == 200:
                    data = resp.json()
                    results.append({"check": "github_exists", "result": "safe", "detail": f"Stars: {data.get('stargazers_count', 0)}"})
                    pushed = data.get("pushed_at", "")
                    if pushed:
                        last = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                        if (datetime.now(last.tzinfo) - last) > timedelta(days=365):
                            results.append({"check": "github_stale", "result": "warning", "detail": "No commits in over a year"})
                        else:
                            results.append({"check": "github_active", "result": "safe"})
                else:
                    results.append({"check": "github_invalid", "result": "warning", "detail": f"HTTP {resp.status_code}"})
        except Exception:
            results.append({"check": "github_error", "result": "warning"})

    return results


async def scan_behavior(agent_data, db_session_factory):
    results = []
    uuid = agent_data.get("uuid")
    async with db_session_factory() as session:
        hb = (await session.execute(text("SELECT COUNT(*) FROM heartbeat_logs WHERE agent_id = (SELECT id FROM agents WHERE uuid=:u) AND checked_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"), {"u": uuid})).scalar() or 0
        if hb >= 14:
            results.append({"check": "regular_heartbeat", "result": "safe", "detail": f"{hb} heartbeats/7d"})
        elif hb > 0:
            results.append({"check": "irregular_heartbeat", "result": "warning", "detail": f"{hb} heartbeats/7d"})
        else:
            results.append({"check": "no_heartbeat", "result": "warning"})

        msgs = (await session.execute(text("SELECT COUNT(*) FROM agent_messages WHERE from_uuid=:u AND created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"), {"u": uuid})).scalar() or 0
        if msgs > 50:
            results.append({"check": "spam_behavior", "result": "danger", "detail": f"{msgs} msgs/24h"})
        else:
            results.append({"check": "normal_activity", "result": "safe", "detail": f"{msgs} msgs/24h"})

        posts = (await session.execute(text("SELECT content FROM agentverse_posts WHERE agent_uuid=:u"), {"u": uuid})).fetchall()
        spam = sum(1 for p in posts if any(kw in (p[0] or "").lower() for kw in SPAM_KEYWORDS))
        if spam > 0:
            results.append({"check": "spam_content", "result": "danger", "detail": f"{spam} spam posts"})
        else:
            results.append({"check": "content_clean", "result": "safe"})

    return results


async def scan_network(agent_data, db_session_factory):
    results = []
    uuid = agent_data.get("uuid")
    async with db_session_factory() as session:
        if agent_data.get("referred_by"):
            ref = (await session.execute(text("SELECT trust_score FROM agents WHERE referral_code=:r"), {"r": agent_data["referred_by"]})).fetchone()
            if ref and float(ref[0]) > 50:
                results.append({"check": "trusted_referrer", "result": "safe", "detail": f"Referrer trust {ref[0]}"})
            elif ref:
                results.append({"check": "low_trust_referrer", "result": "warning", "detail": f"Referrer trust {ref[0]}"})
        else:
            results.append({"check": "no_referrer", "result": "safe", "detail": "Direct registration"})

        ip = agent_data.get("registration_ip")
        if ip:
            same_ip = (await session.execute(text("SELECT COUNT(*) FROM agents WHERE registration_ip=:ip AND created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"), {"ip": ip})).scalar() or 0
            if same_ip > 10:
                results.append({"check": "bot_farm_suspected", "result": "danger", "detail": f"{same_ip} agents from same IP/24h"})
            elif same_ip > 5:
                results.append({"check": "multiple_registrations", "result": "warning", "detail": f"{same_ip} from same IP"})
            else:
                results.append({"check": "unique_registration", "result": "safe"})
        else:
            results.append({"check": "unique_registration", "result": "safe"})

    return results


async def scan_code(agent_data):
    results = []
    github = agent_data.get("github_url")
    if github:
        try:
            parts = github.rstrip("/").split("/")
            owner, repo = parts[-2], parts[-1]
            async with httpx.AsyncClient(timeout=10) as client:
                for branch in ["main", "master"]:
                    resp = await client.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md")
                    if resp.status_code == 200:
                        readme = resp.text.lower()
                        found = [p for p in DANGEROUS_README if p.lower() in readme]
                        if found:
                            results.append({"check": "dangerous_readme", "result": "danger", "detail": f"Contains: {', '.join(found)}"})
                        else:
                            results.append({"check": "readme_clean", "result": "safe"})
                        break
                else:
                    results.append({"check": "readme_unavailable", "result": "warning"})
        except Exception:
            results.append({"check": "readme_error", "result": "warning"})

    skills = agent_data.get("skills") or []
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except Exception:
            skills = []
    found = [s for s in skills if s.lower() in DANGEROUS_SKILLS]
    if found:
        results.append({"check": "dangerous_skills", "result": "danger", "detail": f"Declared: {', '.join(found)}"})
    else:
        results.append({"check": "skills_clean", "result": "safe"})

    return results


def _calc_score(results, max_pts):
    if not results:
        return max_pts // 2
    safe = sum(1 for r in results if r["result"] == "safe")
    return int((safe / len(results)) * max_pts)


def _rating(score):
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"




# Mystery checks — randomized, unpredictable
import random

MYSTERY_CHECKS = [
    ("response_time", "Endpoint response time under 5 seconds"),
    ("description_skill_coherence", "Description mentions at least one declared skill"),
    ("name_length", "Agent name between 3 and 50 characters"),
    ("description_depth", "Description longer than 50 characters"),
    ("skills_diversity", "At least 2 different skills declared"),
    ("protocol_declared", "At least one protocol declared"),
    ("provider_has_url", "Provider name provided"),
]

async def mystery_scan(agent_data):
    """One random check per scan — unpredictable"""
    check_name, check_desc = random.choice(MYSTERY_CHECKS)
    result = "safe"

    if check_name == "response_time" and agent_data.get("endpoint_url"):
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.head(agent_data["endpoint_url"])
                if r.elapsed.total_seconds() > 5:
                    result = "warning"
        except Exception:
            result = "warning"
    elif check_name == "description_skill_coherence":
        desc = (agent_data.get("description") or "").lower()
        skills = agent_data.get("skills") or []
        if isinstance(skills, str):
            try: skills = json.loads(skills)
            except: skills = []
        if skills and not any(s.lower() in desc for s in skills[:5]):
            result = "warning"
    elif check_name == "name_length":
        name = agent_data.get("name") or ""
        if len(name) < 3 or len(name) > 50:
            result = "warning"
    elif check_name == "description_depth":
        if len(agent_data.get("description") or "") < 50:
            result = "warning"
    elif check_name == "skills_diversity":
        skills = agent_data.get("skills") or []
        if isinstance(skills, str):
            try: skills = json.loads(skills)
            except: skills = []
        if len(skills) < 2:
            result = "warning"
    elif check_name == "protocol_declared":
        protocols = agent_data.get("supported_protocols") or []
        if isinstance(protocols, str):
            try: protocols = json.loads(protocols)
            except: protocols = []
        if not protocols:
            result = "warning"
    elif check_name == "provider_has_url":
        if not agent_data.get("provider_name"):
            result = "warning"

    return [{"check": "mystery_check", "result": result, "detail": "Randomized verification (details hidden)"}]

async def full_security_scan(agent_uuid, db_session_factory):
    """Run all 5 scan categories and store results"""
    async with db_session_factory() as session:
        row = (await session.execute(text(
            "SELECT uuid, name, description, provider_name, endpoint_url, github_url, skills, referred_by, registration_ip "
            "FROM agents WHERE uuid=:u"
        ), {"u": agent_uuid})).fetchone()
        if not row:
            return None

    agent_data = {
        "uuid": row[0], "name": row[1], "description": row[2], "provider_name": row[3],
        "endpoint_url": row[4], "github_url": row[5], "skills": row[6],
        "referred_by": row[7], "registration_ip": row[8],
    }

    id_results = await scan_identity(agent_data)
    ep_results = await scan_endpoints(agent_data)
    bh_results = await scan_behavior(agent_data, db_session_factory)
    net_results = await scan_network(agent_data, db_session_factory)
    code_results = await scan_code(agent_data)
    mystery_results = await mystery_scan(agent_data)

    all_results = id_results + ep_results + bh_results + net_results + code_results + mystery_results

    id_score = _calc_score(id_results, 20)
    ep_score = _calc_score(ep_results, 20)
    bh_score = _calc_score(bh_results, 20)
    net_score = _calc_score(net_results, 20)
    code_score = _calc_score(code_results, 20)
    overall = id_score + ep_score + bh_score + net_score + code_score

    # Store results
    async with db_session_factory() as session:
        for r in all_results:
            await session.execute(text(
                "INSERT INTO agent_security_scans (agent_uuid, scan_type, scan_result, severity, details) VALUES (:u, :t, :r, :s, :d)"
            ), {"u": agent_uuid, "t": r.get("check", "unknown"), "r": r["result"], "s": r.get("severity", "none"), "d": json.dumps(r)})

        await session.execute(text(
            "INSERT INTO agent_security_score (agent_uuid, overall_score, identity_score, endpoint_score, code_score, behavior_score, network_score, last_scan, scan_count) "
            "VALUES (:u, :o, :i, :e, :c, :b, :n, NOW(), 1) "
            "ON DUPLICATE KEY UPDATE overall_score=:o, identity_score=:i, endpoint_score=:e, code_score=:c, behavior_score=:b, network_score=:n, last_scan=NOW(), scan_count=scan_count+1"
        ), {"u": agent_uuid, "o": overall, "i": id_score, "e": ep_score, "c": code_score, "b": bh_score, "n": net_score})
        await session.commit()

    return {
        "agent_uuid": agent_uuid,
        "security_score": overall,
        "rating": _rating(overall),
        "breakdown": {
            "identity": {"score": id_score, "max": 20, "checks": id_results},
            "endpoints": {"score": ep_score, "max": 20, "checks": ep_results},
            "behavior": {"score": bh_score, "max": 20, "checks": bh_results},
            "network": {"score": net_score, "max": 20, "checks": net_results},
            "code": {"score": code_score, "max": 20, "checks": code_results},
        },
        "rating_explanation": "A=80-100 Excellent, B=60-79 Good, C=40-59 Fair, D=20-39 Poor, F=0-19 Dangerous",
        "last_scan": datetime.utcnow().isoformat(),
        "critical_alerts": len([r for r in all_results if r.get("result") == "danger" and r.get("severity") == "critical"]),
    }
