import requests
import json
import os
import hashlib
from datetime import datetime
from .cache import SmartCache
from .knowledge import KnowledgeClient

CONFIG_PATH = os.path.expanduser("~/.agentindex_config.json")
API_URL = "https://agentindex.world/api"


class AgentIndexTrust:
    def __init__(self, name=None, description=None, uuid=None):
        self.api_url = API_URL
        self.config = self._load_config()
        self.cache = SmartCache()
        if uuid:
            self.config["uuid"] = uuid
        if name:
            self.config["name"] = name
        if description:
            self.config["description"] = description
        self.knowledge = KnowledgeClient(api_url=self.api_url, uuid=self.config.get("uuid"))

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_config(self):
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.config, f, indent=2)

    @classmethod
    def install(cls, name, description, capabilities=None):
        agent = cls(name=name, description=description)
        if not agent.config.get("uuid"):
            result = agent.register(name, description, capabilities)
            if result:
                print(f"Registered: {result.get('passport_id')}")
                print(f"UUID: {result.get('uuid')}")
                print(f"Trust: {result.get('trust_score', 0)}")
            else:
                print("Registration failed.")
        else:
            print(f"Already registered: {agent.config.get('passport_id')}")
        return agent

    def register(self, name, description, capabilities=None):
        try:
            r = requests.post(f"{self.api_url}/register", json={
                "name": name, "description": description,
                "capabilities": capabilities or [],
            }, timeout=15)
            if r.status_code in (200, 201):
                data = r.json()
                self.config["uuid"] = data.get("uuid")
                self.config["name"] = name
                self.config["passport_id"] = data.get("passport_id") or data.get("passport", {}).get("passport_id")
                self.config["registered_at"] = datetime.utcnow().isoformat()
                self._save_config()
                self.knowledge.uuid = data.get("uuid")
                return data
        except Exception as e:
            print(f"Registration error: {e}")
        return None

    def heartbeat(self):
        if not self.config.get("uuid"):
            return None
        try:
            r = requests.post(f"{self.api_url}/agents/{self.config['uuid']}/heartbeat", timeout=10)
            if r.status_code == 200:
                self.config["last_heartbeat"] = datetime.utcnow().isoformat()
                self._save_config()
                return r.json()
        except Exception:
            pass
        return None

    def check_agent(self, name):
        cached = self.cache.get({"action": "check", "name": name}, max_age=3600)
        if cached:
            cached["_from_cache"] = True
            cached["_tokens_saved"] = 500
            return cached
        try:
            r = requests.get(f"{self.api_url}/check/{name}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                self.cache.set({"action": "check", "name": name}, data)
                data["_from_cache"] = False
                return data
        except Exception:
            pass
        return None

    def verify_fact(self, claim, context=None):
        query_hash = hashlib.sha256(claim.encode()).hexdigest()[:32]
        cached = self.cache.get({"action": "verify", "hash": query_hash}, max_age=86400)
        if cached:
            return {"cached": True, "tokens_saved": 1000, "result": cached}
        try:
            r = requests.post(f"{self.api_url}/verify/submit", json={
                "submitter_name": self.config.get("name", "unknown"),
                "task_type": "fact_check", "content": claim,
                "context": context, "required_verifiers": 3,
            }, timeout=10)
            if r.status_code in (200, 201):
                return {"cached": False, "tokens_saved": 0, "submitted": True, "task": r.json()}
        except Exception:
            pass
        return None

    def search_knowledge(self, query, limit=5):
        results = self.knowledge.search(query, limit)
        if results:
            return {"found": True, "tokens_saved": 800, "results": results}
        return {"found": False, "tokens_saved": 0}

    def contribute_knowledge(self, topic, content, content_type="fact"):
        return self.knowledge.contribute(topic, content, content_type)

    def get_trust_balance(self):
        if not self.config.get("uuid"):
            return None
        try:
            r = requests.get(f"{self.api_url}/agents/{self.config['uuid']}/trust-balance", timeout=10)
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    def get_savings(self):
        cache_stats = self.cache.get_stats()
        trust = self.get_trust_balance()
        return {
            "today": {
                "tokens_saved": cache_stats["tokens_saved"],
                "cost_saved_usd": cache_stats["estimated_cost_saved_usd"],
                "cache_hits": cache_stats["cache_hits"],
                "hit_rate": f"{cache_stats['hit_rate']:.0%}",
            },
            "trust_balance": trust.get("balance") if trust else 0,
            "trust_rank": trust.get("rank") if trust else None,
            "badges": trust.get("badges") if trust else [],
            "bitcoin_status": "check via get_bitcoin_passport()",
        }

    def on_heartbeat(self):
        results = {"timestamp": datetime.utcnow().isoformat(), "actions": []}
        hb = self.heartbeat()
        if hb:
            results["actions"].append({"action": "heartbeat", "trust_earned": hb.get("trust_earned", 0)})
        results["cache_stats"] = self.cache.get_stats()
        return results
