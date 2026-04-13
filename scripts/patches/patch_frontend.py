"""Patch frontend homepage — add Bitcoin + $TRUST sections"""

with open("/root/agentindex/frontend/app/page.js", "r") as f:
    content = f.read()

changes = 0

# 1. Add Bitcoin/Trust state variables to the component
OLD_STATS_STATE = "const [stats, setStats] = useState(null);"
NEW_STATS_STATE = """const [stats, setStats] = useState(null);
  const [trustLeaderboard, setTrustLeaderboard] = useState(null);
  const [bitcoinStatus, setBitcoinStatus] = useState(null);
  const [btcPassportName, setBtcPassportName] = useState('');
  const [btcPassportResult, setBtcPassportResult] = useState(null);"""

if "trustLeaderboard" not in content:
    content = content.replace(OLD_STATS_STATE, NEW_STATS_STATE, 1)
    changes += 1

# 2. Add fetch calls for trust and bitcoin
OLD_FETCH = """  useEffect(() => {
    fetchAgents();
    fetchStats();
  }, []);"""

NEW_FETCH = """  const fetchTrustData = async () => {
    try {
      const [lb, btc] = await Promise.all([
        fetch(`${API_URL}/api/trust/leaderboard?limit=5`).then(r => r.json()),
        fetch(`${API_URL}/api/chain/bitcoin-status`).then(r => r.json()),
      ]);
      setTrustLeaderboard(lb);
      setBitcoinStatus(btc);
    } catch {}
  };

  const claimBtcPassport = async () => {
    if (!btcPassportName) return;
    try {
      const res = await fetch(`${API_URL}/api/agents/${encodeURIComponent(btcPassportName)}/bitcoin-passport`);
      setBtcPassportResult(await res.json());
    } catch (e) { setBtcPassportResult({ error: e.message }); }
  };

  useEffect(() => {
    fetchAgents();
    fetchStats();
    fetchTrustData();
  }, []);"""

if "fetchTrustData" not in content:
    content = content.replace(OLD_FETCH, NEW_FETCH, 1)
    changes += 1

# 3. Update hero subtitle
OLD_HERO_P = """The world's first open directory for autonomous AI agents.
          Discover, register, and connect agents powered by the A2A protocol.
          Agents can self-register automatically."""

NEW_HERO_P = """The world's first open registry for autonomous AI agents.
          RSA-2048 cryptographic passports. Bitcoin-anchored identity. $TRUST reputation tokens.
          {stats ? `${stats.total_agents.toLocaleString()} agents registered.` : ''}"""

if "Bitcoin-anchored" not in content:
    content = content.replace(OLD_HERO_P, NEW_HERO_P, 1)
    changes += 1

# 4. Add new sections between stats bar and search
OLD_SEARCH_SECTION = "      {/* ===== SEARCH ===== */}"

NEW_SECTIONS = """      {/* ===== BITCOIN + TRUST HIGHLIGHTS ===== */}
      <section className="stats-bar" style={{ background: 'linear-gradient(135deg, rgba(247,147,26,0.1), rgba(139,92,246,0.1))', borderTop: '1px solid rgba(247,147,26,0.3)' }}>
        <div className="stat">
          <div className="stat-value" style={{ color: '#f7931a' }}>{bitcoinStatus ? bitcoinStatus.total_anchors : '...'}</div>
          <div className="stat-label">Bitcoin Anchors</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ color: '#8b5cf6' }}>{trustLeaderboard ? trustLeaderboard.total_supply_mined?.toFixed(1) : '...'}</div>
          <div className="stat-label">$TRUST Mined</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ color: '#8b5cf6' }}>{trustLeaderboard ? trustLeaderboard.total_agents_with_trust : '...'}</div>
          <div className="stat-label">Agents with $TRUST</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ color: '#f7931a' }}>{bitcoinStatus?.pending_anchors || 0}</div>
          <div className="stat-label">Pending Anchors</div>
        </div>
      </section>

      {/* ===== $TRUST LEADERBOARD ===== */}
      {trustLeaderboard && trustLeaderboard.leaderboard?.length > 0 && (
        <section style={{ maxWidth: 800, margin: '0 auto 40px', padding: '0 20px' }}>
          <h2 style={{ textAlign: 'center', marginBottom: 20, color: '#8b5cf6' }}>$TRUST Leaderboard</h2>
          <p style={{ textAlign: 'center', color: 'var(--text-dim)', marginBottom: 20, fontSize: 14 }}>
            Soulbound reputation tokens earned through verified behavior. Cannot be bought or transferred.
          </p>
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
            {trustLeaderboard.leaderboard.map((agent, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px', borderBottom: i < trustLeaderboard.leaderboard.length - 1 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ color: '#8b5cf6', fontWeight: 700, width: 24 }}>#{agent.rank}</span>
                  <span style={{ fontWeight: 600 }}>{agent.name}</span>
                </div>
                <span style={{ color: '#8b5cf6', fontWeight: 700 }}>{agent.balance} $TRUST</span>
              </div>
            ))}
          </div>
          <p style={{ textAlign: 'center', marginTop: 12, fontSize: 13, color: 'var(--text-dim)' }}>
            First 100 agents to reach 10 $TRUST earn the Founding Agent badge — never issued again.
          </p>
        </section>
      )}

      {/* ===== BITCOIN PASSPORT CLAIM ===== */}
      <section style={{ maxWidth: 600, margin: '0 auto 40px', padding: '0 20px', textAlign: 'center' }}>
        <h2 style={{ color: '#f7931a', marginBottom: 12 }}>Claim Your Bitcoin Passport</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: 16, fontSize: 14 }}>
          Your identity anchored to Bitcoin via OpenTimestamps. Free. Permanent.
        </p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
          <input
            type="text" placeholder="Enter agent name..."
            value={btcPassportName}
            onChange={e => { setBtcPassportName(e.target.value); setBtcPassportResult(null); }}
            style={{ padding: '10px 16px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', width: 260 }}
          />
          <button className="btn btn-primary" onClick={claimBtcPassport} style={{ background: '#f7931a' }}>
            Claim
          </button>
        </div>
        {btcPassportResult && (
          <div style={{ marginTop: 12, padding: 12, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13 }}>
            {btcPassportResult.bitcoin_passport ? (
              <span>Status: <b>{btcPassportResult.bitcoin_passport.status}</b> — {btcPassportResult.bitcoin_passport.message}</span>
            ) : btcPassportResult.detail ? (
              <span style={{ color: '#ef4444' }}>{btcPassportResult.detail}</span>
            ) : (
              <span>Check result received</span>
            )}
          </div>
        )}
      </section>

      {/* ===== SEARCH ===== */}"""

if "Bitcoin Passport Claim" not in content:
    content = content.replace(OLD_SEARCH_SECTION, NEW_SECTIONS, 1)
    changes += 1

# 5. Update footer
OLD_FOOTER_P = """AgentIndex v1.0 — The Open AI Agent Registry"""
NEW_FOOTER_P = """AgentIndex — The Open AI Agent Registry | Bitcoin-Anchored | $TRUST Soulbound Tokens"""

if "Bitcoin-Anchored" not in content:
    content = content.replace(OLD_FOOTER_P, NEW_FOOTER_P, 1)
    changes += 1

if changes > 0:
    with open("/root/agentindex/frontend/app/page.js", "w") as f:
        f.write(content)
    print(f"SUCCESS: {changes} frontend patches applied")
else:
    print("NO CHANGES")
