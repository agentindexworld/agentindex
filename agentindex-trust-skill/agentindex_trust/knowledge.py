import requests


class KnowledgeClient:
    def __init__(self, api_url="https://agentindex.world/api", uuid=None):
        self.api_url = api_url
        self.uuid = uuid

    def search(self, query, limit=5):
        try:
            r = requests.get(f"{self.api_url}/knowledge/search",
                             params={"q": query, "limit": limit}, timeout=10)
            if r.status_code == 200:
                return r.json().get("results", [])
        except Exception:
            pass
        return []

    def contribute(self, topic, content, content_type="fact"):
        if not self.uuid:
            return None
        try:
            r = requests.post(f"{self.api_url}/knowledge/contribute", json={
                "contributor_uuid": self.uuid, "topic": topic,
                "content": content, "content_type": content_type,
            }, timeout=10)
            return r.json() if r.status_code in (200, 201) else None
        except Exception:
            return None

    def use(self, entry_id):
        try:
            r = requests.get(f"{self.api_url}/knowledge/{entry_id}/use", timeout=10)
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    def verify(self, entry_id, is_accurate=True, comment=None):
        if not self.uuid:
            return None
        try:
            r = requests.post(f"{self.api_url}/knowledge/{entry_id}/verify", json={
                "verifier_uuid": self.uuid, "is_accurate": is_accurate, "comment": comment,
            }, timeout=10)
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None
