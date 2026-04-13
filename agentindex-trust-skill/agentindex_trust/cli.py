import sys
from .core import AgentIndexTrust


def main():
    if len(sys.argv) < 2:
        print("Usage: agentindex <command>")
        print("Commands: install, status, check, heartbeat, search, contribute")
        return

    cmd = sys.argv[1]
    agent = AgentIndexTrust()

    if cmd == "install":
        if len(sys.argv) < 4:
            print("Usage: agentindex install <name> <description>")
            return
        AgentIndexTrust.install(sys.argv[2], " ".join(sys.argv[3:]))

    elif cmd == "status":
        savings = agent.get_savings()
        print(f"Tokens saved: {savings['today']['tokens_saved']}")
        print(f"$TRUST: {savings['trust_balance']}")
        print(f"Rank: {savings['trust_rank']}")
        print(f"Badges: {savings['badges']}")

    elif cmd == "check":
        if len(sys.argv) < 3:
            print("Usage: agentindex check <agent_name>")
            return
        result = agent.check_agent(sys.argv[2])
        if result:
            print(f"Name: {result.get('name')}")
            print(f"Trust: {result.get('trust_score')}")
            print(f"Security: {result.get('security_rating')}")
            print(f"Cached: {result.get('_from_cache', False)}")

    elif cmd == "heartbeat":
        result = agent.heartbeat()
        if result:
            print(f"Status: {result.get('status')}")
            print(f"Trust earned: {result.get('trust_earned')}")

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: agentindex search <query>")
            return
        result = agent.search_knowledge(" ".join(sys.argv[2:]))
        print(f"Found: {result.get('found')}")
        for r in result.get("results", []):
            print(f"  - {r.get('topic')}: {r.get('content', '')[:80]}")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
