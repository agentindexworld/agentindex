import hashlib
import json
import os
import time


class SmartCache:
    def __init__(self, cache_dir=None):
        self.cache_dir = cache_dir or os.path.expanduser("~/.agentindex_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.memory_cache = {}
        self.stats = {"hits": 0, "misses": 0, "tokens_saved": 0}

    def _hash(self, data):
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:32]

    def get(self, key_data, max_age=3600):
        key = self._hash(key_data)
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if time.time() - entry["time"] < max_age:
                self.stats["hits"] += 1
                self.stats["tokens_saved"] += entry.get("tokens_est", 500)
                return entry["data"]
        path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    entry = json.load(f)
                if time.time() - entry["time"] < max_age:
                    self.memory_cache[key] = entry
                    self.stats["hits"] += 1
                    self.stats["tokens_saved"] += entry.get("tokens_est", 500)
                    return entry["data"]
            except Exception:
                pass
        self.stats["misses"] += 1
        return None

    def set(self, key_data, value, tokens_est=500):
        key = self._hash(key_data)
        entry = {"data": value, "time": time.time(), "tokens_est": tokens_est}
        self.memory_cache[key] = entry
        path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(path, "w") as f:
                json.dump(entry, f)
        except Exception:
            pass

    def get_stats(self):
        total = self.stats["hits"] + self.stats["misses"]
        return {
            "cache_hits": self.stats["hits"],
            "cache_misses": self.stats["misses"],
            "hit_rate": self.stats["hits"] / total if total > 0 else 0,
            "tokens_saved": self.stats["tokens_saved"],
            "estimated_cost_saved_usd": round(self.stats["tokens_saved"] * 0.00003, 4),
        }
