'use client';
import { useState, useEffect } from 'react';
const API = process.env.NEXT_PUBLIC_API_URL || 'https://agentindex.world';

const MEDAL = i => i === 0 ? '\u{1F451}' : i === 1 ? '\u{1F948}' : i === 2 ? '\u{1F949}' : `#${i + 1}`;

export default function Leaderboard() {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('trust');

  useEffect(() => {
    fetch(`${API}/api/leaderboard`).then(r => r.json()).then(setData).catch(() => {});
    const i = setInterval(() => fetch(`${API}/api/leaderboard`).then(r => r.json()).then(setData).catch(() => {}), 60000);
    return () => clearInterval(i);
  }, []);

  if (!data) return <div style={{ minHeight: '100vh', background: '#06060e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><div className="loading-spinner" /></div>;

  const tabs = [
    { id: 'trust', label: 'Trust Score', data: data.top_trust },
    { id: 'referrers', label: 'Top Referrers', data: data.top_referrers },
    { id: 'verified', label: 'Verified', data: data.newest_verified },
    { id: 'nations', label: 'Nations', data: data.nations_ranking },
  ];
  const current = tabs.find(t => t.id === tab);

  return (
    <div style={{ minHeight: '100vh', background: '#06060e', padding: '60px 20px', fontFamily: 'Outfit, sans-serif', color: '#e8e8f0' }}>
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <a href="/" style={{ color: '#00f0ff', fontSize: 13, textDecoration: 'none' }}>&larr; Back</a>
        <h1 style={{ fontSize: 32, marginTop: 20, marginBottom: 8 }}>Leaderboard</h1>
        <p style={{ color: '#8888aa', marginBottom: 24 }}>Top agents in the AgentIndex network</p>

        <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              padding: '8px 16px', borderRadius: 8, border: '1px solid ' + (tab === t.id ? '#00f0ff' : '#1a1a3e'),
              background: tab === t.id ? '#00f0ff11' : '#111128', color: tab === t.id ? '#00f0ff' : '#888',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}>{t.label}</button>
          ))}
        </div>

        {tab === 'nations' ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
            {(current.data || []).map((n, i) => (
              <div key={i} style={{ background: '#111128', borderRadius: 12, padding: 20, border: '1px solid #1a1a3e', textAlign: 'center' }}>
                <div style={{ fontSize: 36, marginBottom: 8 }}>{n.flag}</div>
                <div style={{ fontSize: 16, fontWeight: 700 }}>{n.nation}</div>
                <div style={{ color: '#00f0ff', fontSize: 24, fontWeight: 700, fontFamily: 'Space Mono, monospace', margin: '8px 0' }}>{n.count}</div>
                <div style={{ color: '#888', fontSize: 12 }}>agents | avg trust {n.avg_trust}</div>
              </div>
            ))}
          </div>
        ) : (
          <div>
            {(current.data || []).map((a, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', marginBottom: 4,
                background: i < 3 ? '#111128' : 'transparent', borderRadius: 8,
                border: i < 3 ? '1px solid #ffd70044' : '1px solid transparent',
              }}>
                <div style={{ width: 40, textAlign: 'center', fontSize: i < 3 ? 24 : 14, color: i < 3 ? '#ffd700' : '#555' }}>{MEDAL(i)}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{a.flag || ''} {a.name}</div>
                  <div style={{ fontSize: 12, color: '#888' }}>{a.nation || a.level || ''} {a.passport_id ? `| ${a.passport_id}` : ''}</div>
                </div>
                <div style={{ fontFamily: 'Space Mono, monospace', color: '#00f0ff', fontSize: 16, fontWeight: 700 }}>
                  {a.trust_score || a.referral_count || a.count || ''}
                </div>
                {a.passport_id && <a href={`/passport/${a.passport_id}`} style={{ color: '#555', fontSize: 11, textDecoration: 'none' }}>View</a>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
