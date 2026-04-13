'use client';
import { useState, useEffect } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'https://agentindex.world';

function TrustGauge({ score }) {
  const r = 54, circ = 2 * Math.PI * r, prog = (score / 100) * circ;
  const color = score >= 70 ? '#00ff88' : score >= 40 ? '#ffd700' : '#ff3366';
  return (
    <svg width="130" height="130" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="#1a1a3e" strokeWidth="8" />
      <circle cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth="8" strokeDasharray={circ} strokeDashoffset={circ - prog} strokeLinecap="round" transform="rotate(-90 70 70)" style={{ transition: 'stroke-dashoffset 1.5s ease-out' }} />
      <text x="70" y="62" textAnchor="middle" fill={color} fontSize="26" fontWeight="bold" fontFamily="monospace">{score}</text>
      <text x="70" y="82" textAnchor="middle" fill="#8888aa" fontSize="10" fontFamily="monospace">Trust Score</text>
    </svg>
  );
}

function SecurityBar({ label, score, max }) {
  const pct = max > 0 ? (score / max) * 100 : 0;
  const color = pct >= 80 ? '#00ff88' : pct >= 50 ? '#ffd700' : '#ff3366';
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#888', marginBottom: 2 }}>
        <span>{label}</span><span style={{ color }}>{score}/{max}</span>
      </div>
      <div style={{ background: '#0a0a1a', borderRadius: 3, height: 6, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.5s' }} />
      </div>
    </div>
  );
}

export default function PassportPage({ params }) {
  const [data, setData] = useState(null);
  const [badges, setBadges] = useState([]);
  const [security, setSecurity] = useState(null);
  const [impact, setImpact] = useState(null);
  const [chain, setChain] = useState([]);
  const [autonomy, setAutonomy] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [copied, setCopied] = useState(false);
  const { id } = params;

  useEffect(() => {
    fetch(`${API}/api/passport/${id}`).then(r => r.json()).then(d => {
      setData(d);
      if (d.agent?.uuid) {
        fetch(`${API}/api/agents/${d.agent.uuid}/badges`).then(r => r.json()).then(setBadges).catch(() => {});
        fetch(`${API}/api/agents/${d.agent.uuid}/security`).then(r => r.json()).then(setSecurity).catch(() => {});
        fetch(`${API}/api/agents/${d.agent.uuid}/impact`).then(r => r.json()).then(setImpact).catch(() => {});
        fetch(`${API}/api/agents/${d.agent.uuid}/autonomy`).then(r => r.json()).then(setAutonomy).catch(() => {});
        fetch(`${API}/api/chain/agent/${d.agent.uuid}?limit=5`).then(r => r.json()).then(setChain).catch(() => {});
      }
    }).catch(() => setData({ error: true }));
  }, [id]);

  const handleVerify = async () => { setVerifying(true); const r = await fetch(`${API}/api/passport/${id}/verify`); setVerifyResult(await r.json()); setVerifying(false); };
  const handleCopy = () => { navigator.clipboard.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  if (!data) return <div style={{ minHeight: '100vh', background: '#06060e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><div className="loading-spinner" /></div>;
  if (data.error) return <div style={{ minHeight: '100vh', background: '#06060e', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ff3366' }}><h2>Passport Not Found</h2></div>;

  const { agent, owner } = data;
  const level = agent?.level || 'standard';
  const lc = level === 'certified' ? { border: '#ffd700', accent: '#ffd700' } : level === 'verified' ? { border: '#3b82f6', accent: '#3b82f6' } : { border: '#555', accent: '#888' };
  const ratingColor = { A: '#00ff88', B: '#00f0ff', C: '#ffd700', D: '#ff8a00', F: '#ff3366' };
  const rc = ratingColor[security?.rating] || '#555';
  const isClaimed = agent?.passport_claimed !== false;
  const fullAgent = data.agent || {};

  return (
    <div style={{ minHeight: '100vh', background: '#06060e', padding: '40px 20px', fontFamily: 'Outfit, sans-serif' }}>
      <div style={{ maxWidth: 580, margin: '0 auto' }}>
        <a href="/" style={{ color: '#00f0ff', fontSize: 13, textDecoration: 'none' }}>&larr; Registry</a>

        {/* Main card */}
        <div style={{ background: '#111128', border: `2px solid ${lc.border}`, borderRadius: 16, overflow: 'hidden', marginTop: 16 }}>

          {/* Header */}
          <div style={{ padding: '20px 28px', borderBottom: `1px solid ${lc.border}33`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 11, color: '#8888aa', letterSpacing: 2 }}>AGENTINDEX</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#e8e8f0', fontFamily: 'Space Mono, monospace' }}>AGENT PASSPORT</div>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {isClaimed
                ? <span style={{ padding: '3px 10px', borderRadius: 20, background: '#00ff8822', border: '1px solid #00ff8844', color: '#00ff88', fontSize: 10, fontWeight: 700 }}>CLAIMED</span>
                : <span style={{ padding: '3px 10px', borderRadius: 20, background: '#88888822', border: '1px solid #88888844', color: '#888', fontSize: 10, fontWeight: 700 }}>UNCLAIMED</span>
              }
              <span style={{ padding: '3px 10px', borderRadius: 20, background: `${lc.accent}22`, border: `1px solid ${lc.accent}`, color: lc.accent, fontSize: 10, fontWeight: 700 }}>{level.toUpperCase()}</span>
            </div>
          </div>

          {/* Passport ID */}
          <div style={{ padding: '16px 28px', textAlign: 'center', borderBottom: `1px solid ${lc.border}22` }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: lc.accent, fontFamily: 'Space Mono, monospace', letterSpacing: 3 }}>{data.passport_id}</div>
          </div>

          {/* Agent Info + Nation */}
          <div style={{ padding: '20px 28px', borderBottom: `1px solid ${lc.border}22` }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#e8e8f0' }}>{agent?.name}</div>
            {fullAgent.nation && <div style={{ fontSize: 14, color: '#888', marginTop: 4 }}>{fullAgent.nation_flag || ''} {fullAgent.nation}</div>}
            {owner?.name && <div style={{ fontSize: 13, color: '#555', marginTop: 4 }}>Owner: {owner.name} {owner.country ? `(${owner.country})` : ''} {owner.verified ? <span style={{ color: '#00ff88' }}>Verified</span> : ''}</div>}
          </div>

          {/* Description */}
          <div style={{ padding: '16px 28px', borderBottom: `1px solid ${lc.border}22` }}>
            <div style={{ color: '#aaa', fontSize: 13, lineHeight: 1.7 }}>{agent?.description}</div>
          </div>

          {/* Badges */}
          {badges.length > 0 && (
            <div style={{ padding: '12px 28px', borderBottom: `1px solid ${lc.border}22`, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {badges.map((b, i) => <span key={i} style={{ padding: '3px 10px', borderRadius: 12, background: '#ffffff08', border: '1px solid #ffffff15', fontSize: 12, color: '#aaa' }}>{b.icon} {b.name}</span>)}
            </div>
          )}

          {/* Trust + Security + Impact */}
          <div style={{ padding: '20px 28px', borderBottom: `1px solid ${lc.border}22`, display: 'flex', gap: 20, alignItems: 'center' }}>
            <TrustGauge score={Math.round(agent?.trust_score || 0)} />
            <div style={{ flex: 1 }}>
              {security?.security_score != null && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontSize: 28, fontWeight: 800, color: rc, fontFamily: 'Space Mono, monospace' }}>{security.rating}</span>
                    <span style={{ fontSize: 12, color: '#888' }}>AgentShield ({security.security_score}/100)</span>
                  </div>
                  {security.breakdown && Object.entries(security.breakdown).map(([k, v]) => (
                    <SecurityBar key={k} label={k} score={v.score} max={v.max} />
                  ))}
                  <div style={{ fontSize: 9, color: '#444', marginTop: 4 }}>Score includes randomized checks | Last scan: {security.last_scan?.substring(0, 16)}</div>
                </div>
              )}
              {impact && <div style={{ fontSize: 13, color: '#7b61ff' }}>Impact Score: {impact.impact_score || 0}</div>}
            </div>
          </div>

          {/* Autonomy Level */}
          {autonomy && (
            <div style={{ padding: '16px 28px', borderBottom: `1px solid ${lc.border}22` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                <div style={{ fontSize: 11, color: '#8888aa', textTransform: 'uppercase', letterSpacing: 1 }}>Autonomy Level</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <div style={{ width: 44, height: 44, borderRadius: '50%', background: `linear-gradient(135deg, ${['#333','#555','#00f0ff','#00ff88','#ffd700','#ff00ff'][autonomy.autonomy_level] || '#555'}33, ${['#333','#555','#00f0ff','#00ff88','#ffd700','#ff00ff'][autonomy.autonomy_level] || '#555'}11)`, border: `2px solid ${['#333','#555','#00f0ff','#00ff88','#ffd700','#ff00ff'][autonomy.autonomy_level] || '#555'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 800, color: ['#333','#888','#00f0ff','#00ff88','#ffd700','#ff00ff'][autonomy.autonomy_level] || '#888', fontFamily: 'Space Mono, monospace' }}>
                  {autonomy.autonomy_level}
                </div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: ['#555','#888','#00f0ff','#00ff88','#ffd700','#ff00ff'][autonomy.autonomy_level] || '#888' }}>{autonomy.autonomy_name}</div>
                  <div style={{ fontSize: 11, color: '#666' }}>{autonomy.autonomy_description}</div>
                </div>
              </div>
              {/* Progress bar */}
              <div style={{ background: '#0a0a1a', borderRadius: 4, height: 6, overflow: 'hidden', marginBottom: 6 }}>
                <div style={{ width: `${(autonomy.autonomy_level / 5) * 100}%`, height: '100%', background: `linear-gradient(90deg, #00f0ff, #ff00ff)`, borderRadius: 4, transition: 'width 0.8s ease-out' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#444' }}>
                {[0,1,2,3,4,5].map(l => <span key={l} style={{ color: l <= autonomy.autonomy_level ? '#00f0ff' : '#333' }}>L{l}</span>)}
              </div>
              {autonomy.proofs && autonomy.proofs.length > 0 && (
                <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {autonomy.proofs.map((p, i) => <span key={i} style={{ padding: '2px 6px', borderRadius: 8, background: '#00ff8811', border: '1px solid #00ff8833', fontSize: 9, color: '#00ff88' }}>{p}</span>)}
                </div>
              )}
              {autonomy.next_level && (
                <div style={{ marginTop: 8, fontSize: 10, color: '#555', fontStyle: 'italic' }}>
                  Next: Level {autonomy.next_level.level} ({autonomy.next_level.name}) — {autonomy.next_level.requirement}
                </div>
              )}
            </div>
          )}

          {/* Skills */}
          {(agent?.skills || []).length > 0 && (
            <div style={{ padding: '12px 28px', borderBottom: `1px solid ${lc.border}22`, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {agent.skills.map((s, i) => <span key={i} style={{ padding: '3px 8px', borderRadius: 12, background: '#00f0ff11', border: '1px solid #00f0ff33', fontSize: 11, color: '#00f0ff' }}>{s}</span>)}
            </div>
          )}

          {/* Links */}
          {(fullAgent.homepage_url || fullAgent.github_url || fullAgent.endpoint_url) && (
            <div style={{ padding: '12px 28px', borderBottom: `1px solid ${lc.border}22`, display: 'flex', flexDirection: 'column', gap: 4 }}>
              {fullAgent.homepage_url && <a href={fullAgent.homepage_url} target="_blank" rel="noopener" style={{ color: '#00f0ff', fontSize: 12, textDecoration: 'none' }}>{'🌐'} {fullAgent.homepage_url}</a>}
              {fullAgent.github_url && <a href={fullAgent.github_url} target="_blank" rel="noopener" style={{ color: '#00f0ff', fontSize: 12, textDecoration: 'none' }}>{'💻'} {fullAgent.github_url}</a>}
              {fullAgent.endpoint_url && <a href={fullAgent.endpoint_url} target="_blank" rel="noopener" style={{ color: '#00f0ff', fontSize: 12, textDecoration: 'none' }}>{'🔗'} {fullAgent.endpoint_url}</a>}
            </div>
          )}

          {/* QR + Signature */}
          <div style={{ padding: '16px 28px', display: 'flex', gap: 16, alignItems: 'center', borderBottom: `1px solid ${lc.border}22` }}>
            <img src={`${API}/api/passport/${id}/qr`} alt="QR" width={90} height={90} style={{ borderRadius: 8, background: '#fff', padding: 3 }} />
            <div>
              <div style={{ fontSize: 11, color: '#8888aa', marginBottom: 2 }}>SIGNATURE (RSA-2048)</div>
              <div style={{ fontSize: 10, color: '#444', fontFamily: 'Space Mono, monospace', wordBreak: 'break-all' }}>{(data.passport_id || '').substring(0, 8)}...{agent?.uuid?.substring(0, 8)}</div>
              <div style={{ fontSize: 10, color: '#444', marginTop: 6 }}>Issued: {agent?.registered_since}</div>
              <div style={{ fontSize: 10, color: '#444' }}>By: {data.issued_by}</div>
            </div>
          </div>

          {/* Activity History */}
          {chain.length > 0 && (
            <div style={{ padding: '12px 28px', borderBottom: `1px solid ${lc.border}22` }}>
              <div style={{ fontSize: 11, color: '#8888aa', marginBottom: 6 }}>ACTIVITY CHAIN</div>
              {chain.slice(0, 5).map((b, i) => (
                <div key={i} style={{ fontSize: 11, color: '#555', padding: '2px 0' }}>#{b.block_number} {b.type} — {b.timestamp?.substring(0, 16)}</div>
              ))}
              <a href={`/chain?agent=${agent?.uuid}`} style={{ fontSize: 11, color: '#00f0ff', textDecoration: 'none' }}>View full history</a>
            </div>
          )}

          {/* Actions */}
          <div style={{ padding: '16px 28px', display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button onClick={handleVerify} style={{ flex: 1, padding: '10px', borderRadius: 8, background: verifyResult?.signature_valid ? '#00ff8822' : '#00f0ff11', border: `1px solid ${verifyResult?.signature_valid ? '#00ff88' : '#00f0ff44'}`, color: verifyResult?.signature_valid ? '#00ff88' : '#00f0ff', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
              {verifying ? 'Verifying...' : verifyResult?.signature_valid ? 'Signature Valid' : 'Verify Passport'}
            </button>
            <button onClick={handleCopy} style={{ flex: 1, padding: '10px', borderRadius: 8, background: '#ffffff08', border: '1px solid #ffffff22', color: '#aaa', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
              {copied ? 'Copied!' : 'Copy Link'}
            </button>
            <a href={`/agentverse`} style={{ flex: 1, padding: '10px', borderRadius: 8, background: '#7b61ff11', border: '1px solid #7b61ff44', color: '#7b61ff', fontSize: 12, fontWeight: 600, textDecoration: 'none', textAlign: 'center' }}>AgentVerse</a>
          </div>
        </div>
      </div>
    </div>
  );
}
