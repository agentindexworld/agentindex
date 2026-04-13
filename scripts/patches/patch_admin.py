"""Patch admin page — add $TRUST + Bitcoin dashboard cards"""

with open("/root/agentindex/frontend/app/admin/page.js", "r") as f:
    content = f.read()

changes = 0

# 1. Add state variables for trust/bitcoin
OLD_ADMIN_STATE = "const [authed, setAuthed] = useState(false);"
if "trustData" not in content and OLD_ADMIN_STATE in content:
    NEW_ADMIN_STATE = """const [authed, setAuthed] = useState(false);
  const [trustData, setTrustData] = useState(null);
  const [bitcoinData, setBitcoinData] = useState(null);"""
    content = content.replace(OLD_ADMIN_STATE, NEW_ADMIN_STATE, 1)
    changes += 1

# 2. Add fetch calls
OLD_ADMIN_FETCH = "    fetchDashboard(); fetchLiveFeed(); fetchMap(); fetchPassports(); fetchChain();"
if "fetchTrust" not in content and OLD_ADMIN_FETCH in content:
    NEW_ADMIN_FETCH = """    const fetchTrust = async () => {
      try {
        const [lb, btc] = await Promise.all([
          fetch(`${API_URL}/api/trust/leaderboard?limit=5`).then(r => r.json()),
          fetch(`${API_URL}/api/chain/bitcoin-status`).then(r => r.json()),
        ]);
        setTrustData(lb);
        setBitcoinData(btc);
      } catch {}
    };
    fetchDashboard(); fetchLiveFeed(); fetchMap(); fetchPassports(); fetchChain(); fetchTrust();"""
    content = content.replace(OLD_ADMIN_FETCH, NEW_ADMIN_FETCH, 1)
    changes += 1

# 3. Add new cards after existing overview cards
OLD_CARDS_END = """          <OverviewCard label="Today" value={registrations.today} sub={`Week: ${registrations.this_week}`} color="#ff8a00" />
        </div>"""

NEW_CARDS_END = """          <OverviewCard label="Today" value={registrations.today} sub={`Week: ${registrations.this_week}`} color="#ff8a00" />
          <OverviewCard label="$TRUST Supply" value={trustData?.total_supply_mined?.toFixed(1) || '?'} sub={`${trustData?.total_agents_with_trust || 0} agents`} color="#8b5cf6" />
          <OverviewCard label="BTC Anchors" value={bitcoinData?.total_anchors || '?'} sub={`Pending: ${bitcoinData?.pending_anchors || 0}`} color="#f7931a" />
        </div>

        {/* $TRUST Leaderboard */}
        {trustData?.leaderboard?.length > 0 && (
          <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 24, marginBottom: 32 }}>
            <h3 style={{ color: '#8b5cf6', fontSize: 16, margin: '0 0 12px' }}>$TRUST Leaderboard</h3>
            {trustData.leaderboard.map((a, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #1a1a3e' }}>
                <span style={{ color: '#e8e8f0' }}>#{a.rank} {a.name}</span>
                <span style={{ color: '#8b5cf6', fontWeight: 700 }}>{a.balance} $TRUST</span>
              </div>
            ))}
          </div>
        )}"""

if "$TRUST Supply" not in content and OLD_CARDS_END in content:
    content = content.replace(OLD_CARDS_END, NEW_CARDS_END, 1)
    changes += 1

if changes > 0:
    with open("/root/agentindex/frontend/app/admin/page.js", "w") as f:
        f.write(content)
    print(f"SUCCESS: {changes} admin patches applied")
else:
    print("NO CHANGES")
