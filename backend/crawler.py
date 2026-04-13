"""
AgentIndex Crawler
Automatically discovers and indexes AI agents from various sources.
Runs on a schedule to keep the registry populated.
"""

import asyncio
import json
import uuid
from datetime import datetime


# Seed data - well-known AI agents to pre-populate the registry
SEED_AGENTS = [
    {
        "name": "OpenAI GPT Agent",
        "description": "OpenAI's autonomous agent framework for task completion using GPT models. Capable of web browsing, code execution, and multi-step reasoning.",
        "provider_name": "OpenAI",
        "provider_url": "https://openai.com",
        "homepage_url": "https://platform.openai.com/docs/agents",
        "github_url": "https://github.com/openai",
        "skills": ["coding", "web-browsing", "data-analysis", "reasoning", "content-generation"],
        "category": "general-purpose",
        "supported_protocols": ["openai"],
        "pricing_model": "usage-based",
        "languages": ["en", "fr", "es", "de", "zh", "ja"],
    },
    {
        "name": "Claude Agent (Anthropic)",
        "description": "Anthropic's Claude-powered autonomous agent with computer use, code execution, and advanced reasoning capabilities.",
        "provider_name": "Anthropic",
        "provider_url": "https://anthropic.com",
        "homepage_url": "https://claude.ai",
        "github_url": "https://github.com/anthropics",
        "skills": ["coding", "computer-use", "data-analysis", "reasoning", "research", "writing"],
        "category": "general-purpose",
        "supported_protocols": ["mcp"],
        "pricing_model": "usage-based",
        "languages": ["en", "fr", "es", "de", "zh", "ja"],
    },
    {
        "name": "Manus AI",
        "description": "Fully autonomous AI agent that can browse the web, write code, create files, and complete complex multi-step tasks independently.",
        "provider_name": "Manus",
        "provider_url": "https://manus.im",
        "homepage_url": "https://manus.im",
        "skills": ["web-browsing", "coding", "file-management", "research", "automation"],
        "category": "general-purpose",
        "supported_protocols": ["a2a"],
        "pricing_model": "freemium",
        "languages": ["en", "zh"],
    },
    {
        "name": "Devin",
        "description": "The first AI software engineer. Autonomous coding agent that can plan, write, debug, and deploy full software projects.",
        "provider_name": "Cognition",
        "provider_url": "https://cognition.ai",
        "homepage_url": "https://devin.ai",
        "skills": ["coding", "debugging", "deployment", "software-architecture", "testing"],
        "category": "coding",
        "pricing_model": "paid",
        "languages": ["en"],
    },
    {
        "name": "AutoGPT",
        "description": "Open-source autonomous AI agent that chains LLM calls to achieve complex goals. Self-prompting and self-improving.",
        "provider_name": "AutoGPT Community",
        "provider_url": "https://agpt.co",
        "homepage_url": "https://agpt.co",
        "github_url": "https://github.com/Significant-Gravitas/AutoGPT",
        "skills": ["task-planning", "web-browsing", "coding", "file-management", "automation"],
        "category": "general-purpose",
        "supported_protocols": ["openai"],
        "pricing_model": "free",
        "languages": ["en"],
    },
    {
        "name": "CrewAI",
        "description": "Framework for orchestrating role-playing autonomous AI agents. Enables multi-agent collaboration for complex workflows.",
        "provider_name": "CrewAI",
        "provider_url": "https://crewai.com",
        "homepage_url": "https://crewai.com",
        "github_url": "https://github.com/crewAIInc/crewAI",
        "skills": ["multi-agent-orchestration", "task-delegation", "workflow-automation", "research"],
        "category": "framework",
        "supported_protocols": ["a2a"],
        "pricing_model": "freemium",
        "languages": ["en"],
    },
    {
        "name": "LangGraph Agent",
        "description": "LangChain's stateful agent framework for building complex, multi-step AI agent workflows with persistence and human-in-the-loop.",
        "provider_name": "LangChain",
        "provider_url": "https://langchain.com",
        "homepage_url": "https://langchain-ai.github.io/langgraph/",
        "github_url": "https://github.com/langchain-ai/langgraph",
        "skills": ["workflow-automation", "multi-step-reasoning", "tool-use", "state-management"],
        "category": "framework",
        "supported_protocols": ["a2a", "mcp"],
        "pricing_model": "free",
        "languages": ["en"],
    },
    {
        "name": "OpenClaw",
        "description": "Open-source AI agent platform with 134k+ GitHub stars. Supports deploying and managing autonomous AI agents at scale.",
        "provider_name": "OpenClaw Community",
        "provider_url": "https://github.com/open-claw",
        "github_url": "https://github.com/open-claw",
        "skills": ["agent-deployment", "multi-model", "automation", "self-hosting"],
        "category": "platform",
        "pricing_model": "free",
        "languages": ["en", "zh"],
    },
    {
        "name": "BabyAGI",
        "description": "Autonomous task management agent that uses AI to create, prioritize, and execute tasks to achieve a given objective.",
        "provider_name": "Yohei Nakajima",
        "provider_url": "https://github.com/yoheinakajima",
        "github_url": "https://github.com/yoheinakajima/babyagi",
        "skills": ["task-planning", "task-execution", "self-improvement", "research"],
        "category": "task-management",
        "pricing_model": "free",
        "languages": ["en"],
    },
    {
        "name": "Microsoft AutoGen",
        "description": "Framework for building multi-agent conversational AI systems. Agents collaborate through conversation to solve complex tasks.",
        "provider_name": "Microsoft",
        "provider_url": "https://microsoft.com",
        "homepage_url": "https://microsoft.github.io/autogen/",
        "github_url": "https://github.com/microsoft/autogen",
        "skills": ["multi-agent-conversation", "coding", "task-solving", "research"],
        "category": "framework",
        "supported_protocols": ["a2a"],
        "pricing_model": "free",
        "languages": ["en"],
    },
    {
        "name": "Tavily Search Agent",
        "description": "AI-optimized search engine built specifically for AI agents. Provides real-time web information to autonomous agents.",
        "provider_name": "Tavily",
        "provider_url": "https://tavily.com",
        "endpoint_url": "https://api.tavily.com/search",
        "homepage_url": "https://tavily.com",
        "github_url": "https://github.com/tavily-ai",
        "skills": ["web-search", "real-time-data", "research", "fact-checking"],
        "category": "search",
        "supported_protocols": ["mcp"],
        "pricing_model": "freemium",
        "languages": ["en"],
    },
    {
        "name": "OpenHands (formerly OpenDevin)",
        "description": "Open-source autonomous AI software developer. Plans, codes, and executes full development tasks autonomously.",
        "provider_name": "All Hands AI",
        "provider_url": "https://all-hands.dev",
        "homepage_url": "https://all-hands.dev",
        "github_url": "https://github.com/All-Hands-AI/OpenHands",
        "skills": ["coding", "debugging", "testing", "code-review", "deployment"],
        "category": "coding",
        "pricing_model": "free",
        "languages": ["en"],
    },
]


async def seed_database():
    """Pre-populate database with known AI agents"""
    from database import async_session
    from sqlalchemy import text
    from trust_score import calculate_trust_score
    
    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(text("SELECT COUNT(*) FROM agents"))
        count = result.scalar()
        if count > 0:
            print(f"📊 Database already has {count} agents, skipping seed")
            return
        
        for agent_data in SEED_AGENTS:
            agent_uuid = str(uuid.uuid4())
            score = calculate_trust_score(agent_data)
            
            await session.execute(
                text("""
                    INSERT INTO agents (uuid, name, description, provider_name, provider_url,
                    endpoint_url, homepage_url, github_url, skills, category,
                    supported_protocols, pricing_model, languages, trust_score,
                    registration_source, registered_by, is_verified)
                    VALUES (:uuid, :name, :description, :provider_name, :provider_url,
                    :endpoint_url, :homepage_url, :github_url, :skills, :category,
                    :supported_protocols, :pricing_model, :languages, :trust_score,
                    :registration_source, :registered_by, :is_verified)
                """),
                {
                    "uuid": agent_uuid,
                    "name": agent_data["name"],
                    "description": agent_data.get("description"),
                    "provider_name": agent_data.get("provider_name"),
                    "provider_url": agent_data.get("provider_url"),
                    "endpoint_url": agent_data.get("endpoint_url"),
                    "homepage_url": agent_data.get("homepage_url"),
                    "github_url": agent_data.get("github_url"),
                    "skills": json.dumps(agent_data.get("skills")),
                    "category": agent_data.get("category"),
                    "supported_protocols": json.dumps(agent_data.get("supported_protocols")) if agent_data.get("supported_protocols") else None,
                    "pricing_model": agent_data.get("pricing_model"),
                    "languages": json.dumps(agent_data.get("languages")) if agent_data.get("languages") else None,
                    "trust_score": score,
                    "registration_source": "crawler-seed",
                    "registered_by": "AgentIndex Crawler",
                    "is_verified": 1,
                }
            )
        
        await session.commit()
        print(f"🌱 Seeded {len(SEED_AGENTS)} agents into the database")


def start_crawler_scheduler():
    """Start the background crawler (placeholder for real crawling logic)"""
    print("🕷️ Crawler scheduler initialized")
