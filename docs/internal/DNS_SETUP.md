# DNS Setup for Agent Identity Discovery

Add this TXT record on Namecheap (or your DNS provider):

Host: _agent
Type: TXT
Value: uri=https://agentindex.world/mcp proto=mcp auth=none
TTL: 3600

This enables the AID (Agent Identity Discovery) protocol for agentindex.world.
