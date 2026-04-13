"""
Trust Score Calculator for AI Agents
Score from 0 to 100 based on multiple factors
"""
import json

KNOWN_PROVIDERS = ["openai", "anthropic", "google", "meta", "microsoft", "mistral", "huggingface",
                   "langchain", "crewai", "autogpt", "tavily", "cognition", "moonshot", "kimi",
                   "xai", "grok", "perplexity", "deepseek", "cohere", "stability", "replicate",
                   "together", "fireworks", "groq", "nvidia", "apple", "samsung", "baidu", "alibaba"]

def calculate_trust_score(agent_data: dict) -> float:
    """Calculate trust score. Minimum 35 for complete profile."""
    score = 0.0

    # Basic identity (20 points)
    has_name = bool(agent_data.get("name"))
    has_desc = len(agent_data.get("description") or "") > 20
    if has_name:
        score += 5
    desc = agent_data.get("description") or ""
    if len(desc) > 20:
        score += 5
    if len(desc) > 100:
        score += 5
    if len(desc) > 300:
        score += 5

    # Provider (15 points)
    provider = (agent_data.get("provider_name") or "").lower()
    if provider:
        score += 5
        if any(p in provider for p in KNOWN_PROVIDERS):
            score += 10  # Known provider bonus
    if agent_data.get("provider_url"):
        score += 5

    # Connectivity (15 points)
    if agent_data.get("endpoint_url"):
        score += 10
    if agent_data.get("agent_card_url"):
        score += 5

    # Code transparency (10 points)
    if agent_data.get("github_url"):
        score += 10

    # Skills (15 points)
    skills = agent_data.get("skills") or []
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except Exception:
            skills = []
    if len(skills) >= 1:
        score += 5
    if len(skills) >= 3:
        score += 5
    if len(skills) >= 5:
        score += 5

    # Protocols (10 points)
    protocols = agent_data.get("supported_protocols") or []
    if isinstance(protocols, str):
        try:
            protocols = json.loads(protocols)
        except Exception:
            protocols = []
    if len(protocols) > 0:
        score += 5
    if any("a2a" in str(p).lower() for p in protocols):
        score += 5

    # Metadata (10 points)
    if agent_data.get("version"):
        score += 3
    if agent_data.get("homepage_url"):
        score += 4
    if agent_data.get("pricing_model"):
        score += 3

    # Description quality (5 points)
    if desc:
        quality_keywords = ["api", "autonomous", "automat", "integrat", "real-time",
                           "secure", "open-source", "agent", "llm", "gpt", "model",
                           "framework", "platform", "deploy", "orchestrat"]
        matches = sum(1 for kw in quality_keywords if kw.lower() in desc.lower())
        score += min(matches * 1.0, 5)

    return round(min(score, 100), 2)
