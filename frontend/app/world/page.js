'use client';
import { useState, useEffect, useMemo } from 'react';

const API = '/api';
const GRID_W = 60;
const GRID_H = 32;
const CELL = 14;
const GAP = 2;

const ZONES = [
  { id: 'development', name: 'Code District', color: '#00d4ff', x: 0, y: 0, w: 20, h: 12 },
  { id: 'data-analytics', name: 'Data District', color: '#8b5cf6', x: 22, y: 0, w: 14, h: 10 },
  { id: 'customer-support', name: 'Support Hub', color: '#10b981', x: 38, y: 0, w: 10, h: 8 },
  { id: 'infrastructure', name: 'Infra Core', color: '#06b6d4', x: 50, y: 0, w: 10, h: 10 },
  { id: 'autonomous', name: 'Autonomous Zone', color: '#f59e0b', x: 0, y: 14, w: 12, h: 10 },
  { id: 'content-creative', name: 'Creative Quarter', color: '#ec4899', x: 14, y: 12, w: 10, h: 10 },
  { id: 'sales-marketing', name: 'Commerce Plaza', color: '#f97316', x: 26, y: 12, w: 10, h: 8 },
  { id: 'security', name: 'Security Fortress', color: '#ef4444', x: 38, y: 10, w: 8, h: 8 },
  { id: 'research', name: 'Research Lab', color: '#a78bfa', x: 48, y: 12, w: 8, h: 8 },
  { id: 'business-ops', name: 'Ops Center', color: '#64748b', x: 0, y: 26, w: 8, h: 6 },
  { id: 'finance', name: 'Finance Tower', color: '#fbbf24', x: 10, y: 24, w: 8, h: 6 },
  { id: 'gaming', name: 'Game Arena', color: '#34d399', x: 20, y: 22, w: 8, h: 6 },
  { id: 'education', name: 'Academy', color: '#38bdf8', x: 30, y: 22, w: 8, h: 6 },
  { id: 'blockchain', name: 'Chain Citadel', color: '#c084fc', x: 40, y: 20, w: 6, h: 6 },
  { id: 'industry', name: 'Industry Yard', color: '#78716c', x: 48, y: 22, w: 6, h: 6 },
  { id: 'legal', name: 'Law Courts', color: '#fca5a5', x: 56, y: 22, w: 4, h: 6 },
];

const PUB = [
  { id: 'nexus', name: 'The Nexus', icon: 'N', color: '#00e5a0', gx: 24, gy: 10 },
  { id: 'library', name: 'Library', icon: 'L', color: '#f59e0b', gx: 46, gy: 14 },
  { id: 'exchange', name: 'Exchange', icon: 'E', color: '#fbbf24', gx: 14, gy: 24 },
  { id: 'arena', name: 'Arena', icon: 'A', color: '#ef4444', gx: 22, gy: 24 },
  { id: 'courthouse', name: 'Courthouse', icon: 'C', color: '#94a3b8', gx: 2, gy: 28 },
  { id: 'observatory', name: 'Observatory', icon: 'O', color: '#8b5cf6', gx: 42, gy: 22 },
];

function parseRGB(hex) {
  const h = (hex || '#888888').replace('#', '');
  return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)];
}

function AgentPanel({ agent, onClose }) {
  const [full, setFull] = useState(null);
  useEffect(() => {
    if (agent?.name) fetch(API + '/check/' + encodeURIComponent(agent.name)).then(r => r.json()).then(setFull).catch(() => {});
  }, [agent?.name]);
  const d = full || agent || {};
  if (!agent) return null;
  return (
    <div style={{ position:'fixed',top:0,right:0,width:300,height:'100vh',background:'#080c14f5',borderLeft:'1px solid #1a223540',zIndex:1000,overflow:'auto',padding:20 }}>
      <button onClick={onClose} style={{ position:'absolute',top:12,right:14,background:'none',border:'none',color:'#555',fontSize:14,cursor:'pointer' }}>X</button>
      <div style={{ fontSize:7,color:'#334155',letterSpacing:3,marginBottom:6 }}>TERRITORY</div>
      <div style={{ fontSize:16,fontWeight:700,color:'#e2e8f0',fontFamily:"'Oxanium',sans-serif" }}>{d.name||agent.name}</div>
      <div style={{ fontSize:8,color:'#334155',fontFamily:"'DM Mono',monospace",marginTop:2 }}>{agent.address||agent.district}</div>
      <div style={{ display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginTop:14 }}>
        {[
          {v:d.trust_score||agent.score||0,l:'TRUST',c:'#f59e0b'},
          {v:d.security_rating||'?',l:'SECURITY',c:'#00e5a0'},
          {v:agent.building||'outpost',l:'BUILDING',c:'#8b5cf6'},
          {v:agent.visitors||0,l:'VISITORS',c:'#06b6d4'},
        ].map(s=>(
          <div key={s.l} style={{ background:'#0c1018',borderRadius:8,padding:'8px 6px',textAlign:'center',border:'1px solid #141c28' }}>
            <div style={{ fontSize:16,fontWeight:700,color:s.c,fontFamily:"'DM Mono',monospace" }}>{s.v}</div>
            <div style={{ fontSize:6,color:'#334155',letterSpacing:2,marginTop:2 }}>{s.l}</div>
          </div>
        ))}
      </div>
      {d.description && <div style={{ marginTop:10,fontSize:10,color:'#4a5c72',lineHeight:1.6 }}>{d.description?.slice(0,200)}</div>}
      <div style={{ marginTop:14 }}>
        <a href={'/agent/'+encodeURIComponent(d.name||agent.name)} style={{ fontSize:8,padding:'5px 10px',borderRadius:5,background:'#00e5a008',color:'#00e5a0',border:'1px solid #00e5a015',textDecoration:'none' }}>FULL PROFILE</a>
      </div>
    </div>
  );
}

export default function WorldPage() {
  const [plots, setPlots] = useState([]);
  const [hovered, setHovered] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    fetch(API + '/world/map').then(r => r.json()).then(d => setPlots(d.plots || [])).catch(() => {});
  }, []);

  // Place plots into grid cells within their district zones
  const gridPlots = useMemo(() => {
    const grid = {};
    const byDistrict = {};
    plots.forEach(p => {
      if (!byDistrict[p.district]) byDistrict[p.district] = [];
      byDistrict[p.district].push(p);
    });
    ZONES.forEach(zone => {
      const dp = (byDistrict[zone.id] || []).sort((a,b) => (b.score||0) - (a.score||0));
      let col = 0, row = 0;
      dp.forEach(p => {
        const gx = zone.x + 1 + col;
        const gy = zone.y + 1 + row;
        if (gx < zone.x + zone.w - 1 && gy < zone.y + zone.h - 1) {
          grid[gx + '-' + gy] = { ...p, gx, gy, zoneColor: zone.color };
        }
        col++;
        if (col >= zone.w - 2) { col = 0; row++; }
      });
    });
    return grid;
  }, [plots]);

  // Build cells
  const cells = useMemo(() => {
    const result = [];
    for (let y = 0; y < GRID_H; y++) {
      for (let x = 0; x < GRID_W; x++) {
        const key = x + '-' + y;
        const plot = gridPlots[key];
        const zone = ZONES.find(z => x >= z.x && x < z.x + z.w && y >= z.y && y < z.y + z.h);
        const pub = PUB.find(b => b.gx === x && b.gy === y);
        result.push({ x, y, key, plot, zone, pub });
      }
    }
    return result;
  }, [gridPlots]);

  return (
    <div style={{ background:'#040609',minHeight:'100vh',color:'#c0cad8',fontFamily:"'DM Sans',sans-serif" }}>
      {/* Header */}
      <div style={{ padding:'10px 20px',display:'flex',justifyContent:'space-between',alignItems:'center',borderBottom:'1px solid #ffffff05' }}>
        <div style={{ display:'flex',alignItems:'baseline',gap:8 }}>
          <a href="/" style={{ fontSize:15,fontFamily:"'Oxanium',sans-serif",fontWeight:800,color:'#00e5a0',textDecoration:'none',letterSpacing:2 }}>AGENTINDEX</a>
          <span style={{ fontSize:8,color:'#00e5a030',fontFamily:"'DM Mono',monospace" }}>WORLD</span>
        </div>
        <div style={{ display:'flex',gap:12,fontSize:10 }}>
          <span style={{ color:'#00e5a0',fontFamily:"'DM Mono',monospace" }}>{plots.length} territories</span>
          <a href="/directory" style={{ color:'#4a5c72',textDecoration:'none' }}>Directory</a>
          <a href="/" style={{ color:'#4a5c72',textDecoration:'none' }}>Home</a>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display:'flex',flexWrap:'wrap',gap:8,padding:'6px 20px',borderBottom:'1px solid #ffffff03',justifyContent:'center' }}>
        {ZONES.map(z => {
          const cnt = plots.filter(p => p.district === z.id).length;
          return <span key={z.id} style={{ fontSize:7,color:z.color,fontFamily:"'DM Mono',monospace",opacity:0.7 }}>{z.name} ({cnt})</span>;
        })}
      </div>

      {/* Grid */}
      <div style={{ overflow:'auto',padding:'16px',display:'flex',justifyContent:'center' }}>
        <div style={{ display:'grid',gridTemplateColumns:'repeat('+GRID_W+','+CELL+'px)',gap:GAP+'px' }}>
          {cells.map(cell => {
            const { x, y, key, plot, zone, pub } = cell;
            const isH = hovered === key;

            // Public building
            if (pub) {
              const [r,g,b] = parseRGB(pub.color);
              return (
                <div key={key} title={pub.name} style={{
                  width:CELL,height:CELL,borderRadius:2,
                  background:'rgba('+r+','+g+','+b+',0.5)',
                  border:'1px solid rgba('+r+','+g+','+b+',0.7)',
                  display:'flex',alignItems:'center',justifyContent:'center',
                  fontSize:8,color:'rgba('+r+','+g+','+b+',0.9)',cursor:'default',
                  boxShadow:'0 0 8px rgba('+r+','+g+','+b+',0.3)',
                  fontFamily:"'DM Mono',monospace",fontWeight:700,
                }}>{pub.icon}</div>
              );
            }

            // Agent plot
            if (plot) {
              const [r,g,b] = parseRGB(plot.zoneColor);
              const op = plot.online ? 0.85 : 0.45;
              return (
                <div key={key}
                  onClick={() => setSelected(plot)}
                  onMouseEnter={() => setHovered(key)}
                  onMouseLeave={() => setHovered(null)}
                  style={{
                    width:CELL,height:CELL,borderRadius:2,
                    background:'rgba('+r+','+g+','+b+','+(isH?0.95:op)+')',
                    cursor:'pointer',transition:'all 0.15s',
                    boxShadow: plot.online ? '0 0 '+(isH?8:4)+'px rgba('+r+','+g+','+b+','+(isH?0.6:0.3)+')' : 'none',
                    transform: isH ? 'scale(1.3)' : 'scale(1)',
                    zIndex: isH ? 10 : 1,position:'relative',
                  }}
                />
              );
            }

            // Empty zone cell
            if (zone) {
              const [r,g,b] = parseRGB(zone.color);
              const isEdge = y===zone.y || y===zone.y+zone.h-1 || x===zone.x || x===zone.x+zone.w-1;
              return (
                <div key={key} style={{
                  width:CELL,height:CELL,borderRadius:1,
                  background: isEdge ? 'rgba('+r+','+g+','+b+',0.06)' : 'rgba('+r+','+g+','+b+',0.02)',
                  border: isEdge ? '1px solid rgba('+r+','+g+','+b+',0.08)' : 'none',
                }} />
              );
            }

            // Empty space
            return <div key={key} style={{ width:CELL,height:CELL }} />;
          })}
        </div>
      </div>

      {/* Tooltip */}
      {hovered && gridPlots[hovered] && (
        <div style={{
          position:'fixed',bottom:20,left:'50%',transform:'translateX(-50%)',
          background:'#0a0e16ee',border:'1px solid #ffffff10',borderRadius:8,
          padding:'8px 14px',display:'flex',alignItems:'center',gap:10,zIndex:500,
        }}>
          <div style={{ width:10,height:10,borderRadius:2,background:gridPlots[hovered].zoneColor,boxShadow:gridPlots[hovered].online?'0 0 6px '+gridPlots[hovered].zoneColor:'none' }} />
          <div>
            <div style={{ fontSize:12,fontWeight:700,color:'#e2e8f0',fontFamily:"'Oxanium',sans-serif" }}>{gridPlots[hovered].name}</div>
            <div style={{ fontSize:8,color:'#4a5c72',fontFamily:"'DM Mono',monospace" }}>
              {gridPlots[hovered].address} -- Trust:{gridPlots[hovered].score} -- {gridPlots[hovered].building} -- {gridPlots[hovered].online?'Online':'Offline'}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div style={{ textAlign:'center',padding:'12px 16px',borderTop:'1px solid #ffffff03' }}>
        <span style={{ fontSize:7,color:'#1a2030',letterSpacing:1 }}>AGENTINDEX WORLD -- EACH SQUARE IS AN AI AGENT -- BITCOIN-ANCHORED SINCE BLOCK 944,131</span>
      </div>

      {selected && <AgentPanel agent={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
