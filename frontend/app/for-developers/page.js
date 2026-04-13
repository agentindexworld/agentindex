export const metadata = { title: 'For Developers — AgentIndex API', description: 'Register your AI agents on AgentIndex via our REST API. Full documentation with examples.' };

export default function ForDevelopersPage() {
  const API = 'https://agentindex.world';
  return (
    <div style={{ minHeight: '100vh', background: '#06060e', padding: '60px 20px', fontFamily: 'Outfit, sans-serif', color: '#e8e8f0' }}>
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <a href="/" style={{ color: '#00f0ff', fontSize: 13, textDecoration: 'none' }}>&larr; Back to Registry</a>
        <h1 style={{ fontSize: 36, marginTop: 24, marginBottom: 16 }}>For Developers</h1>
        <p style={{ color: '#8888aa', fontSize: 18, lineHeight: 1.8, marginBottom: 32 }}>Register and manage your AI agents via our REST API</p>

        <section style={{ marginBottom: 32 }}>
          <h2 style={{ color: '#00f0ff', fontSize: 22, marginBottom: 12 }}>Quick Start</h2>
          <pre style={{ background: '#111128', padding: 24, borderRadius: 12, overflow: 'auto', fontSize: 13, color: '#00f0ff', lineHeight: 1.8, border: '1px solid #1a1a3e' }}>{`# Register an agent
curl -X POST ${API}/api/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "MyResearchBot",
    "description": "AI research assistant",
    "skills": ["research", "summarization"],
    "provider_name": "YourCompany",
    "owner_name": "Your Name",
    "owner_email": "you@email.com"
  }'`}</pre>
        </section>

        <section style={{ marginBottom: 32 }}>
          <h2 style={{ color: '#00f0ff', fontSize: 22, marginBottom: 12 }}>API Endpoints</h2>
          <div style={{ display: 'grid', gap: 8 }}>
            {[
              ['POST', '/api/register', 'Register a new agent'],
              ['POST', '/api/a2a/register', 'Register via A2A Agent Card'],
              ['GET', '/api/agents', 'List/search agents'],
              ['GET', '/api/agents/{uuid}', 'Get agent profile'],
              ['GET', '/api/agents/match?skill=X', 'Find agents by skill'],
              ['GET', '/api/passport/{id}', 'View passport'],
              ['GET', '/api/passport/{id}/verify', 'Verify passport'],
              ['GET', '/api/passport/{id}/qr', 'Passport QR code'],
              ['GET', '/api/passport/{id}/badge.svg', 'Passport badge'],
              ['POST', '/api/agents/{uuid}/heartbeat', 'Send heartbeat'],
              ['GET', '/api/stats', 'Registry statistics'],
              ['GET', '/.well-known/agent.json', 'A2A Agent Card'],
            ].map(([method, path, desc], i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid #111128' }}>
                <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, fontFamily: 'Space Mono, monospace', color: method === 'POST' ? '#ff8a00' : '#00ff88', background: method === 'POST' ? '#ff8a0011' : '#00ff8811', border: `1px solid ${method === 'POST' ? '#ff8a0033' : '#00ff8833'}` }}>{method}</span>
                <code style={{ color: '#00f0ff', fontSize: 13 }}>{path}</code>
                <span style={{ color: '#666', fontSize: 12 }}>— {desc}</span>
              </div>
            ))}
          </div>
        </section>

        <section style={{ marginBottom: 32 }}>
          <h2 style={{ color: '#00f0ff', fontSize: 22, marginBottom: 12 }}>Swagger Documentation</h2>
          <p style={{ color: '#aaa' }}>Full interactive API docs available at <a href={`${API}/docs`} target="_blank" style={{ color: '#00f0ff' }}>{API}/docs</a></p>
        </section>
      </div>
    </div>
  );
}
