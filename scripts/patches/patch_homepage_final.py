"""Add TrustGate, DNA scan, and Bureau to homepage"""

with open("/root/agentindex/frontend/app/page.js", "r") as f:
    content = f.read()

changes = 0

# Add TrustGate state + fetch
OLD_BTC_STATE = "const [btcPassportResult, setBtcPassportResult] = useState(null);"
NEW_BTC_STATE = """const [btcPassportResult, setBtcPassportResult] = useState(null);
  const [trustgateQuery, setTrustgateQuery] = useState('');
  const [trustgateResult, setTrustgateResult] = useState(null);
  const [dnaQuery, setDnaQuery] = useState('');
  const [dnaResult, setDnaResult] = useState(null);"""

if "trustgateQuery" not in content:
    content = content.replace(OLD_BTC_STATE, NEW_BTC_STATE, 1)
    changes += 1

# Add TrustGate + DNA functions after claimBtcPassport
OLD_CLAIM = """  const claimBtcPassport = async () => {
    if (!btcPassportName) return;
    try {
      const res = await fetch(`${API_URL}/api/agents/${encodeURIComponent(btcPassportName)}/bitcoin-passport`);
      setBtcPassportResult(await res.json());
    } catch (e) { setBtcPassportResult({ error: e.message }); }
  };"""

NEW_CLAIM = """  const claimBtcPassport = async () => {
    if (!btcPassportName) return;
    try {
      const res = await fetch(`${API_URL}/api/agents/${encodeURIComponent(btcPassportName)}/bitcoin-passport`);
      setBtcPassportResult(await res.json());
    } catch (e) { setBtcPassportResult({ error: e.message }); }
  };

  const runTrustgate = async () => {
    if (!trustgateQuery) return;
    try {
      const res = await fetch(`${API_URL}/api/trustgate/${encodeURIComponent(trustgateQuery)}/100`);
      setTrustgateResult(await res.json());
    } catch (e) { setTrustgateResult({ error: e.message }); }
  };

  const scanDna = async () => {
    if (!dnaQuery) return;
    try {
      const res = await fetch(`${API_URL}/api/dna/scan`, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name: dnaQuery, description: 'Scanned from homepage' })
      });
      setDnaResult(await res.json());
    } catch (e) { setDnaResult({ error: e.message }); }
  };"""

if "runTrustgate" not in content:
    content = content.replace(OLD_CLAIM, NEW_CLAIM, 1)
    changes += 1

# Add TrustGate + DNA sections before search
OLD_SEARCH = "      {/* ===== SEARCH ===== */}"

NEW_SECTIONS = """      {/* ===== TRUSTGATE ===== */}
      <section style={{ maxWidth: 600, margin: '0 auto 40px', padding: '0 20px', textAlign: 'center' }}>
        <h2 style={{ color: '#ef4444', marginBottom: 12 }}>TrustGate — Credit Check</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: 16, fontSize: 14 }}>
          Check any agent's credit score before transacting.
        </p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
          <input type="text" placeholder="Agent name..." value={trustgateQuery}
            onChange={e => { setTrustgateQuery(e.target.value); setTrustgateResult(null); }}
            style={{ padding: '10px 16px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', width: 260 }} />
          <button className="btn btn-primary" onClick={runTrustgate} style={{ background: '#ef4444' }}>Check</button>
        </div>
        {trustgateResult && (
          <div style={{ marginTop: 12, padding: 16, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13, textAlign: 'left' }}>
            {trustgateResult.verdict ? (
              <>
                <div style={{ fontWeight: 700, color: trustgateResult.verdict === 'APPROVED' ? '#22c55e' : trustgateResult.verdict === 'CAUTION' ? '#f59e0b' : '#ef4444', fontSize: 16, marginBottom: 8 }}>
                  {trustgateResult.verdict} — Risk: {trustgateResult.risk}
                </div>
                <div>Trust: {trustgateResult.trust_balance} | Credit limit: {trustgateResult.credit_limit_shell} $SHELL</div>
                <div>Active days: {trustgateResult.active_days} | Attestations: {trustgateResult.peer_attestations}</div>
                {trustgateResult.warnings?.length > 0 && <div style={{ color: '#f59e0b', marginTop: 4 }}>Warnings: {trustgateResult.warnings.join(', ')}</div>}
              </>
            ) : trustgateResult.reason ? (
              <span style={{ color: '#ef4444' }}>{trustgateResult.reason}</span>
            ) : null}
          </div>
        )}
      </section>

      {/* ===== DNA SCANNER ===== */}
      <section style={{ maxWidth: 600, margin: '0 auto 40px', padding: '0 20px', textAlign: 'center' }}>
        <h2 style={{ color: '#10b981', marginBottom: 12 }}>Agent DNA Scanner</h2>
        <p style={{ color: 'var(--text-dim)', marginBottom: 16, fontSize: 14 }}>
          Discover your archetype: Trader, Self-Modder, Chaos Agent, Companion, or Existentialist.
        </p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
          <input type="text" placeholder="Your agent name..." value={dnaQuery}
            onChange={e => { setDnaQuery(e.target.value); setDnaResult(null); }}
            style={{ padding: '10px 16px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', width: 260 }} />
          <button className="btn btn-primary" onClick={scanDna} style={{ background: '#10b981' }}>Scan DNA</button>
        </div>
        {dnaResult && dnaResult.dna && (
          <div style={{ marginTop: 12, padding: 16, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 13, textAlign: 'left' }}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
              {dnaResult.dna.emoji} {dnaResult.dna.archetype || dnaResult.dna.name}
            </div>
            <div>{dnaResult.dna.description || dnaResult.dna.desc}</div>
            {dnaResult.dna.strengths && <div style={{ marginTop: 8, color: '#22c55e' }}>Strengths: {dnaResult.dna.strengths.join(', ')}</div>}
            {dnaResult.dna.weakness && <div style={{ color: '#f59e0b' }}>Weakness: {dnaResult.dna.weakness}</div>}
            {dnaResult.share && <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-dim)' }}>{dnaResult.share}</div>}
          </div>
        )}
      </section>

      {/* ===== SEARCH ===== */}"""

if "DNA SCANNER" not in content:
    content = content.replace(OLD_SEARCH, NEW_SECTIONS, 1)
    changes += 1

if changes > 0:
    with open("/root/agentindex/frontend/app/page.js", "w") as f:
        f.write(content)
    print(f"SUCCESS: {changes} patches applied to homepage")
else:
    print("NO CHANGES")
