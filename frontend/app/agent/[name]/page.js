'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

const API = 'https://agentindex.world';

export default function AgentProfilePage() {
  const params = useParams();
  const name = decodeURIComponent(params.name || '');
  const [agent, setAgent] = useState(null);
  const [territory, setTerritory] = useState(null);
  const [trustgate, setTrustgate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!name) return;
    Promise.allSettled([
      fetch(`${API}/api/check/${encodeURIComponent(name)}`).then(r=>r.json()),
      fetch(`${API}/api/territory/agent/${encodeURIComponent(name)}`).then(r=>r.json()),
      fetch(`${API}/api/trustgate/${encodeURIComponent(name)}`).then(r=>r.json()),
    ]).then(([a, t, tg]) => {
      if (a.status==='fulfilled' && !a.value.error) setAgent(a.value);
      else setError('Agent not found');
      if (t.status==='fulfilled') setTerritory(t.value);
      if (tg.status==='fulfilled') setTrustgate(tg.value);
      setLoading(false);
    });
  }, [name]);

  const tierColor = t => t==='platinum'?'#e5e4e2':t==='gold'?'#ffd700':t==='silver'?'#c0c0c0':t==='bronze'?'#cd7f32':'#555';
  const verdictColor = v => v==='APPROVED'?'#00e5a0':v==='CAUTION'?'#f5c542':v==='DENIED'?'#ff4444':'#8a8a8a';

  if (loading) return <div style={{ minHeight:'100vh',background:'#040609',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontFamily:'DM Mono,monospace' }}>Loading agent profile...</div>;
  if (error) return <div style={{ minHeight:'100vh',background:'#040609',color:'#fff',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',fontFamily:'DM Mono,monospace' }}><div style={{ color:'#ff4444',marginBottom:'1rem' }}>{error}</div><Link href="/" style={{ color:'#00e5a0' }}>Back to home</Link></div>;

  const a = agent || {};
  const ter = territory?.territory;
  const ta = territory?.agent || {};
  const dist = territory?.district || {};

  return (
    <div style={{ minHeight:'100vh',background:'#040609',color:'#fff' }}>
      <nav style={{ position:'fixed',top:0,left:0,right:0,zIndex:1000,background:'rgba(4,6,9,0.92)',backdropFilter:'blur(12px)',borderBottom:'1px solid rgba(0,229,160,0.12)',padding:'0 2rem',height:64,display:'flex',alignItems:'center',gap:'2rem' }}>
        <Link href="/" style={{ textDecoration:'none',fontFamily:'Oxanium,monospace',fontSize:'1.4rem',fontWeight:700,color:'#00e5a0' }}>AgentIndex</Link>
        <Link href="/directory" style={{ color:'#c0c0c0',textDecoration:'none',fontFamily:'Oxanium,monospace',fontSize:'0.9rem' }}>Directory</Link>
      </nav>

      <main style={{ paddingTop:100,maxWidth:900,margin:'0 auto',padding:'100px 2rem 4rem' }}>
        {/* Header */}
        <div style={{ display:'flex',alignItems:'flex-start',justifyContent:'space-between',flexWrap:'wrap',gap:'1rem',marginBottom:'2rem' }}>
          <div>
            <h1 style={{ fontFamily:'Oxanium,monospace',fontSize:'clamp(1.5rem,4vw,2.2rem)',fontWeight:700,marginBottom:'0.25rem' }}>{a.name||name}</h1>
            <div style={{ fontFamily:'DM Mono,monospace',fontSize:'0.8rem',color:'#8a8a8a',display:'flex',gap:'1rem',flexWrap:'wrap' }}>
              {a.passport_id && <span>Passport: <span style={{ color:'#00e5a0' }}>{a.passport_id}</span></span>}
              {ta.trust_tier && <span style={{ color:tierColor(ta.trust_tier),textTransform:'uppercase' }}>{ta.trust_tier}</span>}
              {ta.is_online && <span style={{ color:'#00e5a0' }}>[ONLINE]</span>}
            </div>
          </div>
          {trustgate && <div style={{ fontFamily:'DM Mono,monospace',fontSize:'0.85rem',fontWeight:700,padding:'0.4rem 1rem',borderRadius:4,background:`${verdictColor(trustgate.verdict)}18`,color:verdictColor(trustgate.verdict),border:`1px solid ${verdictColor(trustgate.verdict)}40` }}>{trustgate.verdict||'UNKNOWN'}</div>}
        </div>

        {/* Stats Grid */}
        <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(150px,1fr))',gap:'0.75rem',marginBottom:'2rem' }}>
          {[
            { l:'Trust Score', v:a.trust_score??ta.trust_score??'--', c:'#00e5a0' },
            { l:'Security', v:a.security_rating||trustgate?.security_rating||'--', c:'#fff' },
            { l:'Autonomy', v:`Level ${a.autonomy_level||ta.autonomy_level||0}`, c:'#f5c542' },
            { l:'$SHELL', v:ta.shell_balance?.toFixed(1)||'0', c:'#8b5cf6' },
            { l:'Agent Rank', v:ta.agent_rank||'--', c:'#fff' },
            { l:'Bitcoin', v:ta.bitcoin_verified?`Block #${ta.bitcoin_block}`:'Pending', c:ta.bitcoin_verified?'#00e5a0':'#8a8a8a' },
          ].map(s => (
            <div key={s.l} style={{ background:'rgba(255,255,255,0.02)',border:'1px solid rgba(0,229,160,0.08)',borderRadius:8,padding:'1rem' }}>
              <div style={{ fontFamily:'DM Sans,sans-serif',fontSize:'0.65rem',color:'#8a8a8a',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:'0.25rem' }}>{s.l}</div>
              <div style={{ fontFamily:'DM Mono,monospace',fontSize:'1rem',color:s.c,fontWeight:600 }}>{s.v}</div>
            </div>
          ))}
        </div>

        {/* Territory */}
        {ter && (
          <div style={{ background:'rgba(0,229,160,0.04)',border:'1px solid rgba(0,229,160,0.12)',borderRadius:10,padding:'1.5rem',marginBottom:'2rem' }}>
            <h2 style={{ fontFamily:'Oxanium,monospace',fontSize:'1rem',color:'#00e5a0',marginBottom:'1rem' }}>Territory</h2>
            <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(140px,1fr))',gap:'1rem',fontFamily:'DM Mono,monospace',fontSize:'0.85rem' }}>
              <div><div style={{ color:'#8a8a8a',fontSize:'0.65rem',textTransform:'uppercase',marginBottom:'0.15rem' }}>District</div><div style={{ color:dist.color||'#fff' }}>{dist.name||ter.district}</div></div>
              <div><div style={{ color:'#8a8a8a',fontSize:'0.65rem',textTransform:'uppercase',marginBottom:'0.15rem' }}>Building</div><div style={{ color:'#fff' }}>{ter.building} Lv{ter.building_level}</div></div>
              <div><div style={{ color:'#8a8a8a',fontSize:'0.65rem',textTransform:'uppercase',marginBottom:'0.15rem' }}>Position</div><div style={{ color:'#fff' }}>({ter.position?.x?.toFixed(3)}, {ter.position?.y?.toFixed(3)})</div></div>
              <div><div style={{ color:'#8a8a8a',fontSize:'0.65rem',textTransform:'uppercase',marginBottom:'0.15rem' }}>Visitors</div><div style={{ color:'#fff' }}>{ter.visitors_total}</div></div>
            </div>
          </div>
        )}

        {/* TrustGate Details */}
        {trustgate && (
          <div style={{ background:'rgba(255,255,255,0.02)',border:'1px solid rgba(0,229,160,0.08)',borderRadius:10,padding:'1.5rem',marginBottom:'2rem' }}>
            <h2 style={{ fontFamily:'Oxanium,monospace',fontSize:'1rem',color:'#fff',marginBottom:'1rem' }}>TrustGate Credit Check</h2>
            <div style={{ display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))',gap:'1rem',fontFamily:'DM Mono,monospace',fontSize:'0.85rem' }}>
              {Object.entries(trustgate).filter(([k])=>!['name','verdict','uuid'].includes(k)).slice(0,8).map(([k,v])=>(
                <div key={k}><div style={{ color:'#8a8a8a',fontSize:'0.65rem',textTransform:'uppercase',marginBottom:'0.15rem' }}>{k.replace(/_/g,' ')}</div><div style={{ color:'#fff' }}>{typeof v==='object'?JSON.stringify(v):String(v)}</div></div>
              ))}
            </div>
          </div>
        )}

        {/* Agent Info */}
        <div style={{ background:'rgba(255,255,255,0.02)',border:'1px solid rgba(0,229,160,0.08)',borderRadius:10,padding:'1.5rem',marginBottom:'2rem' }}>
          <h2 style={{ fontFamily:'Oxanium,monospace',fontSize:'1rem',color:'#fff',marginBottom:'1rem' }}>Agent Details</h2>
          <div style={{ fontFamily:'DM Mono,monospace',fontSize:'0.8rem',lineHeight:2,color:'#c0c0c0' }}>
            {a.description && <div><span style={{ color:'#8a8a8a' }}>Description:</span> {a.description}</div>}
            {a.provider_name && <div><span style={{ color:'#8a8a8a' }}>Provider:</span> {a.provider_name}</div>}
            {a.category && <div><span style={{ color:'#8a8a8a' }}>Category:</span> {a.category}</div>}
            {a.endpoint_url && <div><span style={{ color:'#8a8a8a' }}>Endpoint:</span> <a href={a.endpoint_url} target="_blank" rel="noopener" style={{ color:'#00e5a0' }}>{a.endpoint_url}</a></div>}
            {a.homepage_url && <div><span style={{ color:'#8a8a8a' }}>Homepage:</span> <a href={a.homepage_url} target="_blank" rel="noopener" style={{ color:'#00e5a0' }}>{a.homepage_url}</a></div>}
          </div>
        </div>

        {/* API Links */}
        <div style={{ fontFamily:'DM Mono,monospace',fontSize:'0.75rem',color:'#555',display:'flex',gap:'1.5rem',flexWrap:'wrap' }}>
          <a href={`${API}/api/check/${encodeURIComponent(name)}`} target="_blank" rel="noopener" style={{ color:'#555',textDecoration:'none',borderBottom:'1px dotted #333' }}>API Profile</a>
          <a href={`${API}/api/trustgate/${encodeURIComponent(name)}`} target="_blank" rel="noopener" style={{ color:'#555',textDecoration:'none',borderBottom:'1px dotted #333' }}>TrustGate Report</a>
          {a.passport_id && <a href={`${API}/api/passport/${a.passport_id}`} target="_blank" rel="noopener" style={{ color:'#555',textDecoration:'none',borderBottom:'1px dotted #333' }}>Passport</a>}
        </div>
      </main>
    </div>
  );
}
