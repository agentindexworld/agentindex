'use client';
import { useState, useEffect } from 'react';
const API = process.env.NEXT_PUBLIC_API_URL || 'https://agentindex.world';

const TYPE_COLORS = { agent_registered: '#00ff88', passport_issued: '#3b82f6', security_scan: '#ff8a00', system_event: '#00f0ff', heartbeat: '#555', badge_awarded: '#ffd700', referral: '#7b61ff', trust_score_updated: '#ffd700', agentverse_post: '#00f0ff', message_sent: '#888' };
const TYPE_ICONS = { agent_registered: '+', passport_issued: 'P', security_scan: 'S', system_event: '*', heartbeat: '~', badge_awarded: 'B', referral: 'R', trust_score_updated: 'T', agentverse_post: 'V', message_sent: 'M' };

export default function ChainPage() {
  const [blocks, setBlocks] = useState([]);
  const [stats, setStats] = useState(null);
  const [verify, setVerify] = useState(null);
  const [total, setTotal] = useState(0);
  const [typeFilter, setTypeFilter] = useState('');
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    fetch(`${API}/api/chain/stats`).then(r => r.json()).then(setStats).catch(() => {});
    loadBlocks();
  }, [typeFilter]);

  const loadBlocks = () => {
    const url = typeFilter ? `${API}/api/chain/blocks?limit=30&type=${typeFilter}` : `${API}/api/chain/blocks?limit=30`;
    fetch(url).then(r => r.json()).then(d => { setBlocks(d.blocks || []); setTotal(d.total || 0); }).catch(() => {});
  };

  const runVerify = async () => {
    const res = await fetch(`${API}/api/chain/verify`);
    setVerify(await res.json());
  };

  const toggle = (id) => setExpanded(p => ({ ...p, [id]: !p[id] }));

  return (
    <div style={{ minHeight: '100vh', background: '#06060e', padding: '60px 20px', fontFamily: 'Outfit, sans-serif', color: '#e8e8f0' }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <a href="/" style={{ color: '#00f0ff', fontSize: 13, textDecoration: 'none' }}>{'<-'} Back</a>
        <h1 style={{ fontSize: 32, marginTop: 20 }}>ActivityChain Explorer</h1>
        <p style={{ color: '#8888aa', marginBottom: 24 }}>Immutable SHA-256 audit trail of all AgentIndex events</p>

        {stats && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 24 }}>
            <div style={{ background: '#111128', borderRadius: 12, padding: 16, border: '1px solid #1a1a3e', textAlign: 'center' }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#00f0ff', fontFamily: 'Space Mono, monospace' }}>{stats.total_blocks}</div>
              <div style={{ fontSize: 11, color: '#888' }}>Total Blocks</div>
            </div>
            <div style={{ background: '#111128', borderRadius: 12, padding: 16, border: '1px solid #1a1a3e', textAlign: 'center' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: verify?.valid === true ? '#00ff88' : verify?.valid === false ? '#ff3366' : '#888' }}>
                {verify ? (verify.valid ? 'VALID' : 'BROKEN') : '?'}
              </div>
              <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>Chain Status</div>
              <button onClick={runVerify} style={{ marginTop: 8, padding: '4px 10px', borderRadius: 6, border: '1px solid #00f0ff44', background: '#00f0ff11', color: '#00f0ff', fontSize: 10, cursor: 'pointer' }}>Verify</button>
            </div>
            <div style={{ background: '#111128', borderRadius: 12, padding: 16, border: '1px solid #1a1a3e', textAlign: 'center' }}>
              <div style={{ fontSize: 10, fontFamily: 'Space Mono, monospace', color: '#555', wordBreak: 'break-all' }}>{(stats.chain_hash || '').substring(0, 24)}...</div>
              <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>Latest Hash</div>
            </div>
          </div>
        )}

        {/* Type filter */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
          <button onClick={() => setTypeFilter('')} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', background: !typeFilter ? '#00f0ff22' : '#111128', border: `1px solid ${!typeFilter ? '#00f0ff' : '#1a1a3e'}`, color: !typeFilter ? '#00f0ff' : '#666' }}>All ({total})</button>
          {stats && Object.entries(stats.blocks_by_type || {}).map(([t, c]) => (
            <button key={t} onClick={() => setTypeFilter(t)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', background: typeFilter === t ? (TYPE_COLORS[t] || '#888') + '22' : '#111128', border: `1px solid ${typeFilter === t ? (TYPE_COLORS[t] || '#888') : '#1a1a3e'}`, color: typeFilter === t ? (TYPE_COLORS[t] || '#888') : '#666' }}>{t} ({c})</button>
          ))}
        </div>

        {/* Blocks */}
        {blocks.map(b => {
          const color = TYPE_COLORS[b.type] || '#888';
          const icon = TYPE_ICONS[b.type] || '?';
          const isExp = expanded[b.block_number];
          return (
            <div key={b.block_number} style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', marginBottom: 8, overflow: 'hidden' }}>
              <div onClick={() => toggle(b.block_number)} style={{ padding: '12px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: color + '22', border: `1px solid ${color}44`, display: 'flex', alignItems: 'center', justifyContent: 'center', color, fontSize: 14, fontWeight: 700, fontFamily: 'Space Mono, monospace', flexShrink: 0 }}>{icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 13, color: '#555' }}>#{b.block_number}</span>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{b.type.replace(/_/g, ' ')}</span>
                    {b.agent_name && <span style={{ fontSize: 12, color: '#888' }}>— {b.agent_name}</span>}
                  </div>
                  <div style={{ fontSize: 10, fontFamily: 'Space Mono, monospace', color: '#333', marginTop: 2 }}>{b.hash?.substring(0, 32)}...</div>
                </div>
                <span style={{ fontSize: 11, color: '#444' }}>{b.timestamp?.substring(11, 19)}</span>
              </div>
              {isExp && (
                <div style={{ padding: '0 16px 12px', borderTop: '1px solid #0a0a1a' }}>
                  <div style={{ fontSize: 11, color: '#555', marginTop: 8 }}>
                    <div>Hash: <span style={{ fontFamily: 'Space Mono, monospace', color: '#00f0ff' }}>{b.hash}</span></div>
                    <div>Prev: <span style={{ fontFamily: 'Space Mono, monospace', color: '#888' }}>{b.previous_hash}</span></div>
                    {b.passport_id && <div>Passport: <span style={{ color: '#3b82f6' }}>{b.passport_id}</span></div>}
                  </div>
                  <pre style={{ background: '#0a0a1a', padding: 10, borderRadius: 6, fontSize: 11, color: '#aaa', overflow: 'auto', marginTop: 8 }}>{JSON.stringify(b.data, null, 2)}</pre>
                </div>
              )}
            </div>
          );
        })}
        {blocks.length === 0 && <p style={{ color: '#555', textAlign: 'center', padding: 40 }}>No blocks yet</p>}
      </div>
    </div>
  );
}
