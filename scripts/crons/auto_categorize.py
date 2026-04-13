#!/usr/bin/env python3
"""
Auto-categorize 26,000+ agents based on name + description.
Runs as cron every 6h.
"""
import mysql.connector
import re
import json
from datetime import datetime

db = mysql.connector.connect(host='127.0.0.1', port=3307, user='agentindex', password=os.environ.get('DB_PASSWORD','agentindex2026'), database='agentindex')
cursor = db.cursor(dictionary=True)

KEYWORDS = {
    'development': {
        'keywords': ['code', 'coding', 'developer', 'programming', 'python', 'javascript', 'typescript', 'react', 'vue', 'angular', 'node', 'django', 'flask', 'laravel', 'ruby', 'rust', 'golang', 'compiler', 'ide', 'vscode', 'debug', 'git', 'github', 'gitlab', 'deploy', 'ci-cd', 'jenkins', 'docker', 'api', 'rest', 'graphql', 'sdk', 'library', 'package', 'npm', 'pip', 'crate', 'lint', 'formatter', 'refactor', 'test', 'unit-test', 'coverage'],
        'subcategories': {
            'code-generation': ['generate', 'copilot', 'autocomplete', 'completion', 'codegen'],
            'code-review': ['review', 'lint', 'quality', 'sonar', 'static-analysis'],
            'debugging': ['debug', 'fix', 'error', 'bug', 'troubleshoot', 'diagnose'],
            'devops': ['deploy', 'ci-cd', 'jenkins', 'pipeline', 'terraform', 'ansible', 'helm'],
            'testing': ['test', 'qa', 'selenium', 'cypress', 'jest', 'pytest', 'coverage'],
            'frontend': ['react', 'vue', 'angular', 'svelte', 'css', 'html', 'ui', 'ux', 'tailwind'],
            'backend': ['api', 'rest', 'graphql', 'server', 'express', 'fastapi', 'django', 'flask'],
            'mobile': ['ios', 'android', 'react-native', 'flutter', 'swift', 'kotlin', 'mobile'],
            'database': ['sql', 'postgres', 'mysql', 'mongo', 'redis', 'database', 'query', 'orm'],
            'documentation': ['doc', 'readme', 'wiki', 'documentation', 'comment', 'jsdoc']
        }
    },
    'data-analytics': {
        'keywords': ['data', 'analytics', 'dataset', 'csv', 'excel', 'pandas', 'numpy', 'statistics', 'visualization', 'chart', 'graph', 'dashboard', 'bi', 'tableau', 'powerbi', 'etl', 'pipeline', 'ml', 'machine-learning', 'deep-learning', 'neural', 'model', 'training', 'inference', 'nlp', 'bert', 'gpt', 'transformer', 'embedding', 'vector', 'rag', 'scrape', 'crawl', 'spider', 'parse', 'extract'],
        'subcategories': {
            'data-analysis': ['analysis', 'analyst', 'insight', 'report', 'statistics'],
            'data-cleaning': ['clean', 'etl', 'transform', 'pipeline', 'normalize'],
            'visualization': ['chart', 'graph', 'dashboard', 'plot', 'tableau', 'powerbi'],
            'machine-learning': ['ml', 'machine-learning', 'model', 'training', 'neural', 'deep'],
            'nlp': ['nlp', 'text', 'language', 'sentiment', 'bert', 'embedding', 'tokeniz'],
            'computer-vision': ['vision', 'image', 'object-detection', 'ocr', 'face', 'yolo'],
            'prediction': ['predict', 'forecast', 'time-series', 'regression', 'classification'],
            'scraping': ['scrape', 'crawl', 'spider', 'extract', 'parse', 'selenium']
        }
    },
    'research': {
        'keywords': ['research', 'paper', 'academic', 'study', 'analysis', 'investigate', 'survey', 'literature', 'review', 'summary', 'summarize', 'abstract', 'citation', 'arxiv', 'scholar', 'fact', 'verify', 'check', 'intelligence', 'competitive', 'market', 'trend'],
        'subcategories': {
            'academic': ['academic', 'paper', 'arxiv', 'scholar', 'citation', 'journal'],
            'market-research': ['market', 'consumer', 'survey', 'industry'],
            'competitive-intel': ['competitive', 'competitor', 'benchmark', 'comparison'],
            'fact-checking': ['fact', 'verify', 'check', 'debunk', 'misinformation'],
            'summarization': ['summary', 'summarize', 'digest', 'brief', 'abstract', 'tldr']
        }
    },
    'content-creative': {
        'keywords': ['write', 'writing', 'content', 'blog', 'article', 'copy', 'creative', 'story', 'narrative', 'poem', 'script', 'image', 'art', 'design', 'illustration', 'photo', 'video', 'animation', 'music', 'audio', 'voice', 'tts', 'stt', 'translate', 'translation', 'localize', 'social', 'twitter', 'instagram', 'tiktok', 'youtube', 'seo', 'keyword', 'ranking'],
        'subcategories': {
            'writing': ['write', 'blog', 'article', 'essay', 'content-writer'],
            'copywriting': ['copy', 'ad', 'headline', 'tagline', 'marketing-copy'],
            'translation': ['translate', 'translation', 'localize', 'multilingual', 'i18n'],
            'image-generation': ['image', 'art', 'illustration', 'midjourney', 'dall-e', 'stable-diffusion'],
            'video': ['video', 'animation', 'edit', 'clip', 'youtube'],
            'social-media': ['social', 'twitter', 'instagram', 'tiktok', 'post', 'schedule'],
            'seo': ['seo', 'keyword', 'ranking', 'serp', 'backlink', 'organic']
        }
    },
    'business-ops': {
        'keywords': ['workflow', 'automation', 'automate', 'schedule', 'calendar', 'email', 'inbox', 'document', 'pdf', 'spreadsheet', 'project', 'task', 'kanban', 'agile', 'scrum', 'meeting', 'transcrib', 'note', 'knowledge', 'wiki', 'notion', 'slack', 'teams', 'productivity'],
        'subcategories': {
            'project-management': ['project', 'kanban', 'agile', 'scrum', 'jira', 'trello'],
            'workflow': ['workflow', 'automation', 'automate', 'n8n', 'zapier', 'make'],
            'email': ['email', 'inbox', 'gmail', 'outlook', 'newsletter'],
            'scheduling': ['calendar', 'schedule', 'booking', 'meeting', 'appointment'],
            'document-processing': ['document', 'pdf', 'spreadsheet', 'excel', 'invoice']
        }
    },
    'finance': {
        'keywords': ['trading', 'trade', 'invest', 'stock', 'crypto', 'bitcoin', 'finance', 'financial', 'bank', 'payment', 'accounting', 'tax', 'audit', 'risk', 'portfolio', 'fund', 'defi', 'yield', 'swap', 'exchange', 'market', 'price', 'chart', 'candle', 'indicator'],
        'subcategories': {
            'trading': ['trading', 'trade', 'stock', 'forex', 'signal', 'strategy'],
            'accounting': ['accounting', 'bookkeeping', 'invoice', 'expense', 'tax'],
            'risk-analysis': ['risk', 'assessment', 'compliance', 'scoring'],
            'fraud-detection': ['fraud', 'anomaly', 'suspicious', 'anti-money'],
            'portfolio': ['portfolio', 'investment', 'allocation', 'rebalance']
        }
    },
    'security': {
        'keywords': ['security', 'secure', 'vulnerability', 'exploit', 'hack', 'pentest', 'penetration', 'audit', 'threat', 'malware', 'virus', 'firewall', 'encryption', 'decrypt', 'password', 'authentication', 'oauth', 'jwt', 'csrf', 'xss', 'sql-injection', 'owasp', 'monitor', 'siem', 'incident', 'response'],
        'subcategories': {
            'vulnerability-scan': ['vulnerability', 'scan', 'cve', 'patch'],
            'penetration-testing': ['pentest', 'penetration', 'exploit', 'hack'],
            'code-audit': ['audit', 'review', 'secure-code', 'owasp'],
            'threat-detection': ['threat', 'malware', 'intrusion', 'detection'],
            'monitoring': ['monitor', 'siem', 'log', 'alert', 'observability']
        }
    },
    'blockchain': {
        'keywords': ['blockchain', 'web3', 'smart-contract', 'solidity', 'ethereum', 'solana', 'polygon', 'nft', 'token', 'defi', 'dao', 'wallet', 'metamask', 'ipfs', 'decentralized', 'on-chain', 'off-chain', 'bridge', 'cross-chain', 'consensus', 'validator', 'staking'],
        'subcategories': {
            'smart-contracts': ['smart-contract', 'solidity', 'vyper', 'hardhat', 'foundry'],
            'defi': ['defi', 'swap', 'liquidity', 'yield', 'lending', 'borrow'],
            'nft': ['nft', 'collectible', 'mint', 'marketplace'],
            'wallet': ['wallet', 'metamask', 'custody', 'key-management'],
            'dao': ['dao', 'governance', 'vote', 'proposal', 'treasury']
        }
    },
    'customer-support': {
        'keywords': ['support', 'help', 'helpdesk', 'ticket', 'customer', 'service', 'chat', 'chatbot', 'bot', 'assistant', 'faq', 'knowledge-base', 'escalat', 'resolve', 'feedback', 'complaint', 'satisfaction'],
        'subcategories': {
            'chatbot': ['chat', 'chatbot', 'conversational', 'dialog', 'bot'],
            'ticket-routing': ['ticket', 'helpdesk', 'zendesk', 'freshdesk', 'routing'],
            'sentiment': ['sentiment', 'feedback', 'satisfaction', 'nps', 'emotion'],
            'voice-assistant': ['voice', 'speech', 'siri', 'alexa', 'ivr', 'call']
        }
    },
    'infrastructure': {
        'keywords': ['framework', 'platform', 'agent-framework', 'langchain', 'crewai', 'autogen', 'swarm', 'orchestrat', 'multi-agent', 'memory', 'vector', 'embedding', 'tool', 'plugin', 'skill', 'mcp', 'protocol', 'a2a', 'openclaw', 'docker', 'kubernetes', 'cloud', 'aws', 'azure', 'gcp'],
        'subcategories': {
            'framework': ['framework', 'langchain', 'crewai', 'autogen', 'llamaindex'],
            'platform': ['platform', 'saas', 'hosted', 'managed', 'cloud-service'],
            'orchestration': ['orchestrat', 'swarm', 'multi-agent', 'workflow-engine'],
            'memory': ['memory', 'vector', 'embedding', 'retrieval', 'rag', 'knowledge'],
            'protocol': ['protocol', 'mcp', 'a2a', 'standard', 'interoperab']
        }
    },
    'autonomous': {
        'keywords': ['autonomous', 'self', 'auto', 'agent', 'agentic', 'goal', 'plan', 'reason', 'decide', 'independent', 'emergent', 'evolve', 'adapt', 'learn'],
        'subcategories': {
            'self-improving': ['self-improving', 'evolve', 'adapt', 'learn', 'optimize'],
            'multi-agent': ['multi-agent', 'swarm', 'collective', 'team', 'collaboration'],
            'planning': ['plan', 'reason', 'strategy', 'decompose', 'chain-of-thought'],
            'decision-making': ['decide', 'decision', 'choose', 'evaluate', 'judge']
        }
    },
    'gaming': {
        'keywords': ['game', 'gaming', 'npc', 'player', 'quest', 'level', 'procedural', 'world', 'narrative', 'story', 'character', 'unity', 'unreal', 'godot', 'steam', 'twitch', 'stream', 'esport'],
        'subcategories': {
            'npc-behavior': ['npc', 'character', 'behavior', 'enemy', 'companion'],
            'procedural-generation': ['procedural', 'generation', 'world', 'terrain', 'dungeon'],
            'game-testing': ['test', 'qa', 'bug', 'balance', 'playtest'],
            'narrative': ['narrative', 'story', 'dialog', 'quest', 'lore']
        }
    },
    'education': {
        'keywords': ['education', 'learn', 'teach', 'tutor', 'course', 'lesson', 'quiz', 'exam', 'student', 'school', 'university', 'academic', 'mentor', 'coach', 'language', 'english', 'spanish', 'french', 'math'],
        'subcategories': {
            'tutoring': ['tutor', 'teach', 'explain', 'homework', 'student'],
            'course-creation': ['course', 'curriculum', 'lesson', 'module'],
            'language-learning': ['language', 'english', 'spanish', 'french', 'german', 'duolingo'],
            'mentoring': ['mentor', 'coach', 'guide', 'career', 'skill']
        }
    },
    'sales-marketing': {
        'keywords': ['sales', 'sell', 'lead', 'prospect', 'crm', 'salesforce', 'hubspot', 'pipeline', 'outreach', 'cold-email', 'marketing', 'campaign', 'conversion', 'funnel', 'landing', 'ad', 'google-ads', 'facebook-ads', 'retarget'],
        'subcategories': {
            'lead-generation': ['lead', 'prospect', 'outreach', 'cold'],
            'crm': ['crm', 'salesforce', 'hubspot', 'pipeline', 'deal'],
            'email-marketing': ['email-marketing', 'newsletter', 'campaign', 'drip'],
            'ad-optimization': ['ad', 'google-ads', 'facebook-ads', 'ppc', 'roi']
        }
    },
    'legal': {
        'keywords': ['legal', 'law', 'lawyer', 'attorney', 'contract', 'agreement', 'clause', 'compliance', 'regulate', 'gdpr', 'hipaa', 'sox', 'patent', 'trademark', 'copyright', 'intellectual-property', 'dispute', 'arbitrat', 'litigation'],
        'subcategories': {
            'contract-analysis': ['contract', 'agreement', 'clause', 'review', 'draft'],
            'legal-research': ['legal-research', 'case-law', 'precedent', 'statute'],
            'compliance': ['compliance', 'gdpr', 'hipaa', 'sox', 'regulate'],
            'privacy': ['privacy', 'gdpr', 'data-protection', 'consent']
        }
    },
    'industry': {
        'keywords': ['healthcare', 'medical', 'health', 'patient', 'diagnosis', 'clinical', 'pharma', 'drug', 'manufacturing', 'factory', 'production', 'quality', 'supply-chain', 'logistics', 'warehouse', 'shipping', 'real-estate', 'property', 'construction', 'building', 'agriculture', 'farm', 'crop', 'soil', 'energy', 'power', 'grid', 'solar', 'wind', 'oil', 'gas'],
        'subcategories': {
            'healthcare': ['health', 'medical', 'patient', 'clinical', 'diagnosis', 'pharma'],
            'manufacturing': ['manufacturing', 'factory', 'production', 'quality-control'],
            'supply-chain': ['supply-chain', 'logistics', 'warehouse', 'shipping', 'inventory'],
            'real-estate': ['real-estate', 'property', 'construction', 'building', 'lease'],
            'agriculture': ['agriculture', 'farm', 'crop', 'soil', 'irrigation'],
            'energy': ['energy', 'power', 'grid', 'solar', 'wind', 'renewable']
        }
    }
}

def categorize_agent(name, description, skills=None):
    skills_text = ''
    if skills:
        if isinstance(skills, list):
            skills_text = ' '.join(str(s) for s in skills)
        elif isinstance(skills, dict):
            skills_text = ' '.join(str(v) for v in skills.values())
        else:
            skills_text = str(skills)
    text = "{} {} {}".format(name, description or '', skills_text).lower()
    text = re.sub(r'[^a-z0-9\s-]', ' ', text)

    scores = {}
    for cat, data in KEYWORDS.items():
        score = sum(1 for kw in data['keywords'] if kw in text)
        if score > 0:
            scores[cat] = score

    if not scores:
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        return {'category': 'infrastructure', 'subcategory': 'platform', 'confidence': 0.1, 'tags': [], 'slug': slug}

    best_cat = max(scores, key=scores.get)
    confidence = min(scores[best_cat] / 5, 1.0)

    best_sub = None
    best_sub_score = 0
    for sub, sub_keywords in KEYWORDS[best_cat].get('subcategories', {}).items():
        sub_score = sum(1 for kw in sub_keywords if kw in text)
        if sub_score > best_sub_score:
            best_sub = sub
            best_sub_score = sub_score

    if not best_sub:
        subs = list(KEYWORDS[best_cat].get('subcategories', {}).keys())
        best_sub = subs[0] if subs else 'general'

    tags = []
    all_kws = KEYWORDS[best_cat]['keywords']
    for kw in all_kws:
        if kw in text and len(tags) < 10:
            tags.append(kw)

    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

    return {
        'category': best_cat,
        'subcategory': best_sub,
        'confidence': confidence,
        'tags': tags[:10],
        'slug': slug
    }

def calculate_agent_rank(agent):
    rank = 0
    if agent.get('description'): rank += 5
    if agent.get('skills'): rank += 5
    if agent.get('github_url') or agent.get('endpoint_url'): rank += 5
    if agent.get('category_slug'): rank += 5
    if agent.get('short_description'): rank += 5
    if agent.get('passport_claimed'): rank += 10
    if agent.get('is_verified'): rank += 10
    rank += 5
    if agent.get('last_heartbeat'): rank += 10
    score = int(agent.get('trust_score') or 0)
    rank += min(score // 10, 10)
    impact = float(agent.get('impact_score') or 0)
    rank += min(int(impact), 15)
    return min(rank, 100)

def get_trust_tier(rank):
    if rank >= 90: return 'platinum'
    if rank >= 70: return 'gold'
    if rank >= 50: return 'silver'
    if rank >= 30: return 'bronze'
    return 'unverified'

# Main
print("=== Auto-Categorization - {} ===".format(datetime.utcnow().isoformat()))

cursor.execute("""
    SELECT uuid, name, description, skills, trust_score, impact_score,
           passport_claimed, is_verified, last_heartbeat, github_url, endpoint_url,
           short_description, category_slug
    FROM agents
    WHERE auto_categorized = 0 OR category_slug IS NULL
    LIMIT 5000
""")
agents = cursor.fetchall()
print("Found {} agents to categorize".format(len(agents)))

categorized = 0
for agent in agents:
    skills_data = None
    if agent.get('skills'):
        try:
            skills_data = json.loads(agent['skills']) if isinstance(agent['skills'], str) else agent['skills']
        except:
            skills_data = None

    result = categorize_agent(agent['name'], agent.get('description', ''), skills_data)
    rank = calculate_agent_rank(agent)
    tier = get_trust_tier(rank)

    cursor.execute("""
        UPDATE agents SET
            category_slug = %s,
            subcategory_slug = %s,
            auto_categorized = 1,
            categorization_confidence = %s,
            slug = %s,
            agent_rank = %s,
            trust_tier = %s
        WHERE uuid = %s
    """, (result['category'], result['subcategory'], result['confidence'],
          result['slug'], rank, tier, agent['uuid']))

    for tag in result['tags']:
        try:
            cursor.execute("INSERT IGNORE INTO agent_tags (agent_uuid, tag) VALUES (%s, %s)", (agent['uuid'], tag))
        except:
            pass

    categorized += 1
    if categorized % 500 == 0:
        db.commit()
        print("  Categorized {}...".format(categorized))

db.commit()

cursor.execute("""
    UPDATE agent_taxonomy t SET agent_count = (
        SELECT COUNT(*) FROM agents a
        WHERE a.category_slug = t.category_slug AND a.subcategory_slug = t.subcategory_slug
    )
""")
db.commit()

print("\nCategorized {} agents".format(categorized))
cursor.execute("SELECT category_slug, COUNT(*) as c FROM agents WHERE category_slug IS NOT NULL GROUP BY category_slug ORDER BY c DESC")
for row in cursor.fetchall():
    print("  {}: {}".format(row['category_slug'], row['c']))

cursor.execute("SELECT trust_tier, COUNT(*) as c FROM agents GROUP BY trust_tier ORDER BY c DESC")
print("\nTrust Tiers:")
for row in cursor.fetchall():
    print("  {}: {}".format(row['trust_tier'], row['c']))

cursor.close()
db.close()
