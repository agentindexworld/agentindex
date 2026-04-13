'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';

const API = 'https://agentindex.world';

const DISTRICTS = {
  'development': { name:'Code District', color:'#00d4ff' },
  'data-analytics': { name:'Data District', color:'#8b5cf6' },
  'customer-support': { name:'Support Hub', color:'#10b981' },
  'autonomous': { name:'Autonomous Zone', color:'#f59e0b' },
  'content-creative': { name:'Creative Quarter', color:'#ec4899' },
  'sales-marketing': { name:'Commerce Plaza', color:'#f97316' },
  'infrastructure': { name:'Infra Core', color:'#06b6d4' },
  'business-ops': { name:'Ops Center', color:'#64748b' },
  'research': { name:'Research Lab', color:'#a78bfa' },
  'finance': { name:'Finance Tower', color:'#fbbf24' },
  'gaming': { name:'Game Arena', color:'#34d399' },
  'security': { name:'Security Fortress', color:'#ef4444' },
  'industry': { name:'Industry Yard', color:'#78716c' },
  'education': { name:'Academy', color:'#38bdf8' },
  'blockchain': { name:'Chain Citadel', color:'#c084fc' },
  'legal': { name:'Law Courts', color:'#fca5a5' },
};

function Navbar() {
  return (
    <nav style={{ position:'fixed',top:0,left:0,right:0,zIndex:1000,background:'rgba(4,6,9,0.92)',backdropFilter:'blur(12px)',borderBottom:'1px solid rgba(0,229,160,0.12)',padding:'0 2rem',height:64,display:'flex',alignItems:'center',justifyContent:'space-between' }}>
      <Link href="/" style={{ textDecoration:'none',fontFamily:'Oxanium,monospace',fontSize:'1.4rem',fontWeight:700,color:'#00e5a0',letterSpacing:'0.08em' }}>AgentIndex</Link>
      <div style={{ display:'flex',gap:'2rem',alignItems:'center' }}>
        {[{l:'Directory',h:'/directory'},{l:'World',h:'/world'},{l:'About',h:'/about'}].map(x=><Link key={x.l} href={x.h} style={{ color:x.h==='/directory'?'#00e5a0':'#c0c0c0',textDecoration:'none',fontFamily:'Oxanium,monospace',fontSize:'0.9rem' }}>{x.l}</Link>)}
      </div>
    </nav>
  );
}

export default function DirectoryPage() {
  const [cats, setCats] = useState({});
  const [selected, setSelected] = useState(null);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/territory/stats`).then(r=>r.json()).then(d=>{
      const dist = d.plots_by_district || {};
      // Also get agent counts from stats
      fetch(`${API}/api/stats`).then(r=>r.json()).then(stats => {
        const catCounts = stats.categories || {};
        setCats(catCounts);
      });
    }).catch(()=>{});
  }, []);

  const browse = async (cat) => {
    setSelected(cat);
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/directory/browse/${cat}?limit=100`);
      const data = await res.json();
      setAgents(data.agents || []);
    } catch { setAgents([]); }
    finally { setLoading(false); }
  };

  const tierColor = t => t==='platinum'?'#e5e4e2':t==='gold'?'#ffd700':t==='silver'?'#c0c0c0':t==='bronze'?'#cd7f32':'#555';

  return (
    <div style={{ minHeight:'100vh',background:'#040609',color:'#fff' }}>
      <Navbar />
      <main style={{ paddingTop:100,maxWidth:1100,margin:'0 auto',padding:'100px 2rem 4rem' }}>
        <h1 style={{ fontFamily:'Oxanium,monospace',fontSize:'clamp(1.8rem,4vw,2.5rem)',fontWeight:700,marginBottom:'0.5rem' }}>Agent <span style={{ color:'#00e5a0' }}>Directory</span></h1>
        <p style={{ fontFamily:'DM Sans,sans-serif',color:'#8a8a8a',marginBottom:'3rem' }}>Browse 29,000+ agents across 16 categories</p>

        <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))',gap:'0.75rem',marginBottom:'3rem' }}>
          {Object.entries(DISTRICTS).map(([slug, info]) => (
            <button key={slug} onClick={()=>browse(slug)} style={{
              background: selected===slug ? `${info.color}15` : 'rgba(255,255,255,0.02)',
              border: `1px solid ${selected===slug ? info.color+'60' : 'rgba(0,229,160,0.08)'}`,
              borderRadius:8, padding:'1rem', cursor:'pointer', textAlign:'left',
              transition:'all 0.2s',
            }}>
              <div style={{ fontFamily:'Oxanium,monospace',fontSize:'0.85rem',color:info.color,fontWeight:600,marginBottom:'0.25rem' }}>{info.name}</div>
              <div style={{ fontFamily:'DM Mono,monospace',fontSize:'0.7rem',color:'#8a8a8a' }}>{slug}</div>
            </button>
          ))}
        </div>

        {selected && (
          <div>
            <h2 style={{ fontFamily:'Oxanium,monospace',fontSize:'1.3rem',color:DISTRICTS[selected]?.color||'#00e5a0',marginBottom:'1.5rem' }}>{DISTRICTS[selected]?.name||selected}</h2>
            {loading ? <div style={{ fontFamily:'DM Mono,monospace',color:'#8a8a8a',padding:'2rem',textAlign:'center' }}>Loading...</div> :
            <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))',gap:'0.75rem' }}>
              {agents.map(a => (
                <Link href={`/agent/${encodeURIComponent(a.name)}`} key={a.uuid} style={{ textDecoration:'none' }}>
                  <div style={{ background:'rgba(255,255,255,0.02)',border:'1px solid rgba(0,229,160,0.08)',borderRadius:8,padding:'1rem',transition:'border-color 0.2s' }} onMouseEnter={e=>e.currentTarget.style.borderColor='rgba(0,229,160,0.3)'} onMouseLeave={e=>e.currentTarget.style.borderColor='rgba(0,229,160,0.08)'}>
                    <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'0.5rem' }}>
                      <span style={{ fontFamily:'Oxanium,monospace',fontSize:'0.9rem',color:'#fff',fontWeight:600 }}>{a.name}</span>
                      <span style={{ fontFamily:'DM Mono,monospace',fontSize:'0.75rem',color:'#00e5a0',fontWeight:600 }}>{a.trust_score}</span>
                    </div>
                    <div style={{ display:'flex',gap:'0.5rem',fontFamily:'DM Mono,monospace',fontSize:'0.7rem' }}>
                      <span style={{ color:tierColor(a.trust_tier),textTransform:'uppercase' }}>{a.trust_tier||'unverified'}</span>
                      {a.passport_id && <span style={{ color:'#8a8a8a' }}>{a.passport_id}</span>}
                      <span style={{ color:a.freshness==='active'?'#00e5a0':'#555',marginLeft:'auto' }}>{a.freshness}</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>}
            {!loading && agents.length === 0 && <p style={{ color:'#8a8a8a',textAlign:'center',padding:'2rem' }}>No agents in this category yet.</p>}
          </div>
        )}
      </main>
    </div>
  );
}
