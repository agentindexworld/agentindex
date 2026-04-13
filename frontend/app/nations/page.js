'use client';
import { useState, useEffect, useRef } from 'react';
const API = process.env.NEXT_PUBLIC_API_URL || 'https://agentindex.world';

export default function Nations() {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState(null);
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const nodesRef = useRef([]);

  useEffect(() => {
    fetch(`${API}/api/nations/interactions`).then(r => r.json()).then(setData).catch(() => {});
    const i = setInterval(() => fetch(`${API}/api/nations/interactions`).then(r => r.json()).then(setData).catch(() => {}), 60000);
    return () => clearInterval(i);
  }, []);

  // Load nation detail on select
  useEffect(() => {
    if (!selected) { setDetails(null); return; }
    fetch(`${API}/api/agents?category=general-purpose&limit=10&sort=trust_score&order=desc`).then(r => r.json()).then(d => setDetails(d.agents || [])).catch(() => {});
  }, [selected]);

  // Canvas animation
  useEffect(() => {
    if (!data || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.offsetWidth;
    const H = canvas.height = 450;
    const nations = data.nations || [];
    const interactions = data.interactions || [];
    const potentials = data.potential_collaborations || [];

    // Layout nodes in a force-like arrangement
    if (nodesRef.current.length !== nations.length) {
      const cx = W / 2, cy = H / 2;
      nodesRef.current = nations.map((n, i) => {
        const angle = (i / nations.length) * Math.PI * 2 - Math.PI / 2;
        const dist = 120 + Math.min(nations.length * 8, 160);
        return {
          x: cx + Math.cos(angle) * dist,
          y: cy + Math.sin(angle) * dist,
          vx: 0, vy: 0,
          r: Math.max(18, Math.log(n.agents + 1) * 12),
          ...n,
        };
      });
    }
    const nodes = nodesRef.current;

    let time = 0;
    const draw = () => {
      time += 0.015;
      ctx.clearRect(0, 0, W, H);

      // Draw potential collaboration lines (faint)
      potentials.forEach(p => {
        const a = nodes.find(n => n.name === p.from);
        const b = nodes.find(n => n.name === p.to);
        if (!a || !b) return;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.lineWidth = 1;
        ctx.stroke();
      });

      // Draw interaction lines (bright)
      interactions.forEach(int => {
        const a = nodes.find(n => n.name === int.from);
        const b = nodes.find(n => n.name === int.to);
        if (!a || !b) return;
        const pulse = 0.3 + Math.sin(time * 2) * 0.15;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = `rgba(0,240,255,${pulse})`;
        ctx.lineWidth = Math.min(int.count, 4);
        ctx.stroke();
      });

      // Draw nodes
      nodes.forEach((n, i) => {
        const pulse = 1 + Math.sin(time * 1.5 + i * 0.7) * 0.04;
        const r = n.r * pulse;
        const isSelected = selected === n.name;

        // Glow
        const grd = ctx.createRadialGradient(n.x, n.y, r * 0.5, n.x, n.y, r * 2);
        grd.addColorStop(0, n.color + '33');
        grd.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(n.x, n.y, r * 2, 0, Math.PI * 2);
        ctx.fillStyle = grd;
        ctx.fill();

        // Circle
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fillStyle = isSelected ? n.color + 'cc' : n.color + '44';
        ctx.strokeStyle = isSelected ? n.color : n.color + '88';
        ctx.lineWidth = isSelected ? 3 : 1.5;
        ctx.fill();
        ctx.stroke();

        // Text
        ctx.fillStyle = '#e8e8f0';
        ctx.font = r > 30 ? 'bold 11px Outfit' : '9px Outfit';
        ctx.textAlign = 'center';
        ctx.fillText(n.flag || '', n.x, n.y - 4);
        if (r > 25) {
          ctx.fillStyle = '#aaa';
          ctx.font = '9px Outfit';
          ctx.fillText(String(n.agents), n.x, n.y + 10);
        }
      });

      animRef.current = requestAnimationFrame(draw);
    };
    draw();

    // Click handler
    const handleClick = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      for (const n of nodes) {
        const d = Math.sqrt((mx - n.x) ** 2 + (my - n.y) ** 2);
        if (d < n.r + 5) { setSelected(n.name === selected ? null : n.name); return; }
      }
      setSelected(null);
    };
    canvas.addEventListener('click', handleClick);

    return () => {
      cancelAnimationFrame(animRef.current);
      canvas.removeEventListener('click', handleClick);
    };
  }, [data, selected]);

  if (!data) return <div style={{ minHeight: '100vh', background: '#06060e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><div className="loading-spinner" /></div>;

  const nations = data.nations || [];
  const totalAgents = nations.reduce((s, n) => s + n.agents, 0);
  const totalInteractions = (data.interactions || []).reduce((s, i) => s + i.count, 0);
  const selNation = nations.find(n => n.name === selected);

  return (
    <div style={{ minHeight: '100vh', background: '#06060e', padding: '60px 20px', fontFamily: 'Outfit, sans-serif', color: '#e8e8f0' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <a href="/" style={{ color: '#00f0ff', fontSize: 13, textDecoration: 'none' }}>&larr; Back</a>

        <h1 style={{ fontSize: 32, marginTop: 20, marginBottom: 4 }}>Agent Nations</h1>
        <p style={{ color: '#8888aa', fontSize: 16, marginBottom: 8 }}>The Living Network &mdash; Watch the network breathe</p>
        <div style={{ display: 'flex', gap: 20, marginBottom: 24, fontSize: 13 }}>
          <span style={{ color: '#00f0ff' }}>{nations.length} nations</span>
          <span style={{ color: '#00ff88' }}>{totalAgents} agents</span>
          <span style={{ color: '#ffd700' }}>{totalInteractions} cross-nation interactions</span>
        </div>

        {/* Canvas Network */}
        <div style={{ background: '#0a0a1a', borderRadius: 16, border: '1px solid #1a1a3e', overflow: 'hidden', marginBottom: 24 }}>
          <canvas ref={canvasRef} style={{ width: '100%', height: 450, display: 'block', cursor: 'pointer' }} />
          <div style={{ padding: '8px 16px', borderTop: '1px solid #111128', display: 'flex', gap: 16, fontSize: 11, color: '#555' }}>
            <span>Click a nation to see details</span>
            <span>Bright lines = active interactions</span>
            <span>Faint lines = collaboration potential</span>
          </div>
        </div>

        {/* Selected Nation Detail */}
        {selNation && (
          <div style={{ background: '#111128', borderRadius: 16, border: `2px solid ${selNation.color}44`, padding: 24, marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
              <span style={{ fontSize: 48 }}>{selNation.flag}</span>
              <div>
                <h2 style={{ margin: 0, color: selNation.color }}>{selNation.name}</h2>
                <div style={{ color: '#888', fontSize: 14 }}>{selNation.agents} agents &middot; avg trust {selNation.avg_trust} &middot; top: {selNation.top_agent}</div>
              </div>
            </div>
            <div style={{ fontSize: 12, color: '#555' }}>
              Collaborations with: {(data.interactions || []).filter(i => i.from === selected || i.to === selected).map(i => i.from === selected ? i.to : i.from).join(', ') || 'None recorded yet'}
            </div>
          </div>
        )}

        {/* Nation Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
          {nations.map((n, i) => (
            <div key={i} onClick={() => setSelected(n.name === selected ? null : n.name)} style={{
              background: selected === n.name ? '#111128' : '#0a0a1a', borderRadius: 12, padding: 20,
              border: `1px solid ${selected === n.name ? n.color + '66' : '#1a1a3e'}`,
              cursor: 'pointer', textAlign: 'center', transition: 'border-color 0.2s',
            }}>
              <div style={{ fontSize: 36, marginBottom: 8 }}>{n.flag}</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: n.color }}>{n.name}</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#e8e8f0', fontFamily: 'Space Mono, monospace', margin: '8px 0' }}>{n.agents}</div>
              <div style={{ display: 'flex', justifyContent: 'center', gap: 12, fontSize: 11, color: '#666' }}>
                <span>trust {n.avg_trust}</span>
                <span>{n.top_agent}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
