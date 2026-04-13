'use client';
import { useState, useEffect } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://agentindex.world';

export default function AgentProfile({ params }) {
  const [agent, setAgent] = useState(null);
  const { uuid } = params;

  useEffect(() => {
    fetch(`${API_URL}/api/agents/${uuid}`)
      .then(r => r.json())
      .then(setAgent)
      .catch(() => setAgent({ error: true }));
  }, [uuid]);

  if (!agent) return (
    <div style={{ minHeight: '100vh', background: '#06060e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="loading-spinner" />
    </div>
  );

  if (agent.error) return (
    <div style={{ minHeight: '100vh', background: '#06060e', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ff3366' }}>
      <h2>Agent Not Found</h2>
    </div>
  );

  const skills = agent.skills || [];
  const passportId = agent.passport_id;

  return (
    <div style={{ minHeight: '100vh', background: '#06060e', padding: '40px 20px', fontFamily: 'Outfit, sans-serif' }}>
      <div style={{ maxWidth: 700, margin: '0 auto' }}>
        <a href="/" style={{ color: '#00f0ff', fontSize: 13, textDecoration: 'none', marginBottom: 20, display: 'block' }}>
          &larr; Back to Registry
        </a>

        <div style={{ background: '#111128', borderRadius: 16, border: '1px solid #1a1a3e', padding: 32 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
            <div>
              <h1 style={{ color: '#e8e8f0', fontSize: 28, margin: 0 }}>{agent.name}</h1>
              {agent.provider_name && <div style={{ color: '#8888aa', fontSize: 14, marginTop: 4 }}>by {agent.provider_name}</div>}
            </div>
            <div style={{
              padding: '6px 14px', borderRadius: 20,
              background: agent.is_active ? '#00ff8822' : '#ff336622',
              color: agent.is_active ? '#00ff88' : '#ff3366',
              fontSize: 12, fontWeight: 600,
            }}>
              {agent.is_active ? 'Active' : 'Inactive'}
            </div>
          </div>

          <p style={{ color: '#aaa', lineHeight: 1.6 }}>{agent.description}</p>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '16px 0' }}>
            {skills.map((s, i) => (
              <span key={i} style={{
                padding: '4px 10px', borderRadius: 12,
                background: '#00f0ff11', border: '1px solid #00f0ff33',
                fontSize: 12, color: '#00f0ff',
              }}>{s}</span>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, margin: '24px 0' }}>
            <div style={{ background: '#0a0a1a', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 11, color: '#8888aa', marginBottom: 4 }}>Trust Score</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: '#00f0ff', fontFamily: 'Space Mono, monospace' }}>{agent.trust_score}</div>
            </div>
            <div style={{ background: '#0a0a1a', borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: 11, color: '#8888aa', marginBottom: 4 }}>Category</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: '#e8e8f0' }}>{agent.category || 'general-purpose'}</div>
            </div>
          </div>

          {agent.github_url && (
            <a href={agent.github_url} target="_blank" rel="noopener noreferrer"
              style={{ color: '#00f0ff', fontSize: 13, display: 'block', marginBottom: 8 }}>
              GitHub Repository &rarr;
            </a>
          )}
          {agent.homepage_url && (
            <a href={agent.homepage_url} target="_blank" rel="noopener noreferrer"
              style={{ color: '#00f0ff', fontSize: 13, display: 'block', marginBottom: 8 }}>
              Homepage &rarr;
            </a>
          )}

          {passportId && (
            <div style={{ marginTop: 24, padding: 16, background: '#0a162844', border: '1px solid #3b82f644', borderRadius: 12 }}>
              <div style={{ fontSize: 12, color: '#3b82f6', marginBottom: 8, fontWeight: 600 }}>AGENTINDEX PASSPORT</div>
              <a href={`/passport/${passportId}`} style={{
                color: '#e8e8f0', fontSize: 18, fontFamily: 'Space Mono, monospace',
                textDecoration: 'none', fontWeight: 700,
              }}>
                {passportId} &rarr;
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
