'use client';
import { useState, useEffect, useCallback, useRef } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

function getToken() { if (typeof window === 'undefined') return null; return sessionStorage.getItem('admin_token'); }
function authHeaders() { const t = getToken(); return t ? { Authorization: `Bearer ${t}` } : {}; }

const FLAG = code => { if (!code) return ''; const c = code.toUpperCase(); return String.fromCodePoint(...[...c].map(ch => 0x1F1E6 + ch.charCodeAt(0) - 65)); };

// Contabo datacenter in Nuremberg
const SERVER_LAT = 49.4521;
const SERVER_LON = 11.0767;

function LoginForm({ onLogin }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const handleSubmit = async (e) => {
    e.preventDefault(); setLoading(true); setError('');
    try {
      const res = await fetch(`${API_URL}/api/admin/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) });
      if (!res.ok) { setError('Invalid password'); setLoading(false); return; }
      const data = await res.json(); sessionStorage.setItem('admin_token', data.token); onLogin();
    } catch { setError('Connection failed'); }
    setLoading(false);
  };
  return (
    <div style={{ minHeight: '100vh', background: '#06060e', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Outfit, sans-serif' }}>
      <form onSubmit={handleSubmit} style={{ background: '#111128', borderRadius: 16, border: '1px solid #1a1a3e', padding: 40, width: 360 }}>
        <h2 style={{ color: '#e8e8f0', fontSize: 22, margin: '0 0 8px', textAlign: 'center' }}>Admin Dashboard</h2>
        <p style={{ color: '#8888aa', fontSize: 13, textAlign: 'center', marginBottom: 24 }}>AgentIndex Registry</p>
        <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Enter admin password"
          style={{ width: '100%', padding: '12px 16px', borderRadius: 8, border: '1px solid #1a1a3e', background: '#0a0a1a', color: '#e8e8f0', fontSize: 14, marginBottom: 16, boxSizing: 'border-box' }} />
        {error && <div style={{ color: '#ff3366', fontSize: 13, marginBottom: 12 }}>{error}</div>}
        <button type="submit" disabled={loading} style={{ width: '100%', padding: '12px', borderRadius: 8, border: 'none', cursor: 'pointer', background: '#00f0ff', color: '#06060e', fontSize: 14, fontWeight: 700, opacity: loading ? 0.6 : 1 }}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  );
}

// ============================================================
// LEAFLET WORLD MAP
// ============================================================
function WorldMap({ mapData, agentsMapData }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const linesRef = useRef([]);
  const agentMarkersRef = useRef([]);
  const leafletRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [showAgents, setShowAgents] = useState(true);
  const [showLive, setShowLive] = useState(true);

  // Load Leaflet CSS + JS dynamically (client only)
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // CSS
    if (!document.getElementById('leaflet-css')) {
      const link = document.createElement('link');
      link.id = 'leaflet-css';
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);
    }

    // Pulse animation CSS
    if (!document.getElementById('pulse-css')) {
      const style = document.createElement('style');
      style.id = 'pulse-css';
      style.textContent = `
        @keyframes leaflet-pulse {
          0% { transform: scale(1); opacity: 0.8; }
          100% { transform: scale(3.5); opacity: 0; }
        }
        .pulse-ring {
          border-radius: 50%;
          animation: leaflet-pulse 2s ease-out infinite;
        }
        @keyframes flash-in {
          0% { transform: scale(3); opacity: 1; }
          100% { transform: scale(1); opacity: 0; }
        }
        .flash-ring {
          border-radius: 50%;
          animation: flash-in 0.6s ease-out forwards;
        }
        .leaflet-container { background: #0a0a1a !important; border-radius: 16px; }
        .leaflet-control-attribution { font-size: 9px !important; background: rgba(10,10,26,0.6) !important; color: #444 !important; }
        .leaflet-control-attribution a { color: #555 !important; }
        .map-overlay-stats {
          position: absolute; top: 12px; right: 12px; z-index: 1000;
          background: rgba(10,10,26,0.85); border: 1px solid #1a1a3e;
          border-radius: 12px; padding: 14px 18px; backdrop-filter: blur(8px);
        }
      `;
      document.head.appendChild(style);
    }

    // JS — load from CDN
    if (window.L) {
      leafletRef.current = window.L;
      setReady(true);
    } else {
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.onload = () => {
        leafletRef.current = window.L;
        setReady(true);
      };
      document.head.appendChild(script);
    }
  }, []);

  // Initialize map once
  useEffect(() => {
    if (!ready || !mapRef.current || mapInstanceRef.current) return;
    const L = leafletRef.current;

    const map = L.map(mapRef.current, {
      center: [20, 0],
      zoom: 2,
      scrollWheelZoom: false,
      zoomControl: true,
      minZoom: 2,
      maxZoom: 12,
      worldCopyJump: true,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    // Server marker (Nuremberg)
    const serverIcon = L.divIcon({
      className: '',
      html: '<div style="width:12px;height:12px;background:#00f0ff;border-radius:50%;border:2px solid #fff;box-shadow:0 0 12px #00f0ff;"></div>',
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });
    L.marker([SERVER_LAT, SERVER_LON], { icon: serverIcon })
      .addTo(map)
      .bindPopup('<div style="font-family:monospace;font-size:12px;"><b style="color:#00f0ff;">AgentIndex Server</b><br/>Nuremberg, Germany</div>');

    mapInstanceRef.current = map;

    return () => { map.remove(); mapInstanceRef.current = null; };
  }, [ready]);

  // Update markers when mapData changes
  useEffect(() => {
    if (!ready || !mapInstanceRef.current || !mapData) return;
    const L = leafletRef.current;
    const map = mapInstanceRef.current;
    const now = Date.now();

    // Clear old markers and lines
    markersRef.current.forEach(m => map.removeLayer(m));
    markersRef.current = [];
    linesRef.current.forEach(l => map.removeLayer(l));
    linesRef.current = [];

    if (!showLive) return;

    // Deduplicate by IP (keep most recent)
    const byIp = {};
    (mapData.live_connections || []).forEach(c => {
      if (!c.lat || !c.lon) return;
      if (!byIp[c.ip] || new Date(c.timestamp) > new Date(byIp[c.ip].timestamp)) {
        byIp[c.ip] = c;
      }
    });
    const connections = Object.values(byIp);

    connections.forEach(c => {
      const ageSec = (now - new Date(c.timestamp).getTime()) / 1000;
      const isNew = ageSec < 120;
      const isOld = ageSec > 3600;
      const opacity = isOld ? 0.3 : 1;

      if (c.is_agent) {
        // Agent: green pulsing marker
        const pulseHtml = `
          <div style="position:relative;width:20px;height:20px;">
            <div class="pulse-ring" style="position:absolute;top:2px;left:2px;width:16px;height:16px;background:rgba(0,255,136,0.25);"></div>
            ${isNew ? '<div class="flash-ring" style="position:absolute;top:-4px;left:-4px;width:28px;height:28px;background:rgba(255,255,255,0.4);"></div>' : ''}
            <div style="position:absolute;top:5px;left:5px;width:10px;height:10px;background:#00ff88;border-radius:50%;box-shadow:0 0 8px #00ff88;opacity:${opacity};"></div>
          </div>`;
        const icon = L.divIcon({ className: '', html: pulseHtml, iconSize: [20, 20], iconAnchor: [10, 10] });
        const ago = ageSec < 60 ? 'just now' : ageSec < 3600 ? `${Math.round(ageSec / 60)}m ago` : `${Math.round(ageSec / 3600)}h ago`;
        const marker = L.marker([c.lat, c.lon], { icon })
          .addTo(map)
          .bindPopup(`<div style="font-family:monospace;font-size:12px;line-height:1.6;">
            <b style="color:#00ff88;">&#x1F916; ${c.agent_name || 'AI Agent'}</b><br/>
            ${c.city ? c.city + ', ' : ''}${c.country || ''}<br/>
            <span style="color:#888;">${c.endpoint || ''}</span><br/>
            <span style="color:#555;">${ago}</span>
          </div>`);
        markersRef.current.push(marker);

        // Connection line to server (curved)
        if (ageSec < 1800) {
          const mid = [(c.lat + SERVER_LAT) / 2 + 8, (c.lon + SERVER_LON) / 2];
          const line = L.polyline(
            [[c.lat, c.lon], mid, [SERVER_LAT, SERVER_LON]],
            { color: '#00ff88', weight: 1.5, opacity: Math.max(0.1, 0.5 - ageSec / 3600), dashArray: '6 8', className: '' }
          ).addTo(map);
          linesRef.current.push(line);
        }
      } else {
        // Human: small grey dot
        const dotHtml = `<div style="width:8px;height:8px;background:#555;border-radius:50%;opacity:${opacity};${isNew ? 'box-shadow:0 0 6px #aaa;' : ''}"></div>`;
        const icon = L.divIcon({ className: '', html: dotHtml, iconSize: [8, 8], iconAnchor: [4, 4] });
        const ago = ageSec < 60 ? 'just now' : ageSec < 3600 ? `${Math.round(ageSec / 60)}m ago` : `${Math.round(ageSec / 3600)}h ago`;
        const marker = L.marker([c.lat, c.lon], { icon })
          .addTo(map)
          .bindPopup(`<div style="font-family:monospace;font-size:12px;line-height:1.6;">
            <b>&#x1F464; Visitor</b><br/>
            ${c.city ? c.city + ', ' : ''}${c.country || ''}<br/>
            <span style="color:#555;">${ago}</span>
          </div>`);
        markersRef.current.push(marker);
      }
    });
  }, [ready, mapData, showLive]);

  // Registered agents layer (static, loaded once)
  useEffect(() => {
    if (!ready || !mapInstanceRef.current || !agentsMapData) return;
    const L = leafletRef.current;
    const map = mapInstanceRef.current;

    agentMarkersRef.current.forEach(m => map.removeLayer(m));
    agentMarkersRef.current = [];

    if (!showAgents) return;

    (agentsMapData.registered_agents || []).forEach(a => {
      if (!a.lat || !a.lon) return;
      const color = a.level === 'verified' || a.level === 'certified' ? '#ffd700' : '#ff3366';
      const glow = a.level === 'verified' || a.level === 'certified' ? 'box-shadow:0 0 6px #ffd700;' : '';
      const dotHtml = `<div style="width:7px;height:7px;background:${color};border-radius:50%;opacity:0.7;${glow}"></div>`;
      const icon = L.divIcon({ className: '', html: dotHtml, iconSize: [7, 7], iconAnchor: [3, 3] });
      const marker = L.marker([a.lat, a.lon], { icon })
        .addTo(map)
        .bindPopup(`<div style="font-family:monospace;font-size:11px;line-height:1.5;">
          <b style="color:${color};">&#x1F534; ${a.name}</b><br/>
          ${a.country || 'Unknown'} &middot; Trust: ${a.trust_score}<br/>
          <span style="color:#00f0ff;">${a.passport_id || 'No passport'}</span><br/>
          <span style="color:#555;">Source: ${a.source}</span>
        </div>`);
      agentMarkersRef.current.push(marker);
    });
  }, [ready, agentsMapData, showAgents]);

  const summary = mapData?.last_24h_summary || {};
  const countryCount = (summary.countries || []).length;
  const top5 = (summary.countries || []).slice(0, 5);
  const latestAgents = (mapData?.live_connections || []).filter(c => c.is_agent).slice(0, 5);
  const agentsTotal = agentsMapData?.total || 0;
  const agentsWithLoc = agentsMapData?.with_location || 0;
  const now = Date.now();

  return (
    <div style={{ background: '#0a0a1a', borderRadius: 16, border: '1px solid #1a1a3e', overflow: 'hidden', marginBottom: 32 }}>
      {/* Title */}
      <div style={{ padding: '16px 24px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ color: '#e8e8f0', fontSize: 16, margin: 0 }}>World Map — Live Agent Discovery</h3>
      </div>

      {/* Map container */}
      <div style={{ position: 'relative', margin: '12px 24px' }}>
        <div ref={mapRef} style={{ width: '100%', height: 450, borderRadius: 16, overflow: 'hidden' }} />
        {/* Overlay stats */}
        <div className="map-overlay-stats">
          <div style={{ fontSize: 13, color: '#ff3366', marginBottom: 6, fontWeight: 600 }}>&#x1F534; {agentsWithLoc} agents registered</div>
          <div style={{ fontSize: 13, color: '#00ff88', marginBottom: 6 }}>&#x1F7E2; {summary.agent_connections || 0} AI visits today</div>
          <div style={{ fontSize: 13, color: '#00f0ff', marginBottom: 6 }}>&#x1F30D; {countryCount} countries</div>
          <div style={{ fontSize: 13, color: '#8888aa', marginBottom: 8 }}>&#x1F4E1; {summary.total_connections || 0} connections (24h)</div>
          <div style={{ borderTop: '1px solid #1a1a3e', paddingTop: 8 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 11, color: '#aaa', marginBottom: 4 }}>
              <input type="checkbox" checked={showAgents} onChange={e => setShowAgents(e.target.checked)} style={{ accentColor: '#ff3366' }} />
              Registered agents ({agentsWithLoc})
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 11, color: '#aaa' }}>
              <input type="checkbox" checked={showLive} onChange={e => setShowLive(e.target.checked)} style={{ accentColor: '#00ff88' }} />
              Live connections
            </label>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{ padding: '16px 24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, borderTop: '1px solid #1a1a3e' }}>
        <div>
          <div style={{ fontSize: 12, color: '#8888aa', marginBottom: 10, fontWeight: 600 }}>TOP COUNTRIES (24h)</div>
          {top5.map((c, i) => {
            const maxCount = top5[0]?.count || 1;
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 16, width: 24 }}>{FLAG(c.code)}</span>
                <span style={{ fontSize: 12, color: '#aaa', width: 80 }}>{c.country}</span>
                <div style={{ flex: 1, background: '#111128', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                  <div style={{ width: `${(c.count / maxCount) * 100}%`, height: '100%', background: '#00f0ff', borderRadius: 3 }} />
                </div>
                <span style={{ fontSize: 11, color: '#666', width: 30, textAlign: 'right' }}>{c.count}</span>
              </div>
            );
          })}
          {top5.length === 0 && <div style={{ fontSize: 12, color: '#555' }}>No geo data yet</div>}
        </div>
        <div>
          <div style={{ fontSize: 12, color: '#8888aa', marginBottom: 10, fontWeight: 600 }}>LATEST AGENT DISCOVERIES</div>
          {latestAgents.map((a, i) => {
            const ago = Math.round((now - new Date(a.timestamp).getTime()) / 60000);
            const agoStr = ago < 1 ? 'just now' : ago < 60 ? `${ago}m ago` : `${Math.round(ago / 60)}h ago`;
            return (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid #111128' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: '#00ff88', fontSize: 14 }}>&#x1F916;</span>
                  <span style={{ fontSize: 12, color: '#e8e8f0' }}>{a.agent_name || 'Agent'}</span>
                  {a.country_code && <span style={{ fontSize: 13 }}>{FLAG(a.country_code)}</span>}
                </div>
                <span style={{ fontSize: 11, color: '#555' }}>{agoStr}</span>
              </div>
            );
          })}
          {latestAgents.length === 0 && <div style={{ fontSize: 12, color: '#555' }}>No AI agent visits yet</div>}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// DASHBOARD COMPONENTS
// ============================================================
function OverviewCard({ label, value, sub, color }) {
  return (
    <div style={{ background: '#111128', borderRadius: 12, padding: 24, border: '1px solid #1a1a3e' }}>
      <div style={{ fontSize: 12, color: '#8888aa', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
      <div style={{ fontSize: 32, fontWeight: 700, color: color || '#e8e8f0', fontFamily: 'Space Mono, monospace' }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: '#8888aa', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function CrawlerCard({ name, data, onRunNow }) {
  const [running, setRunning] = useState(false);
  const status = data?.status || 'idle';
  const statusIcon = status === 'running' ? '\u{1F504}' : status === 'error' ? '\u{1F534}' : '\u{1F7E2}';
  const handleRun = async () => {
    setRunning(true);
    try {
      const map = { github: 'github', huggingface: 'huggingface', a2a_scanner: 'a2a', awesome_lists: 'awesome', openclaw: 'openclaw' };
      await fetch(`${API_URL}/api/admin/crawl/${map[name]}`, { method: 'POST', headers: authHeaders() });
      onRunNow();
    } catch {}
    setRunning(false);
  };
  return (
    <div style={{ background: '#111128', borderRadius: 12, padding: 20, border: '1px solid #1a1a3e' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: '#e8e8f0' }}>{statusIcon} {name.replace('_', ' ')}</div>
        <button onClick={handleRun} disabled={running || status === 'running'} style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', background: '#00f0ff11', border: '1px solid #00f0ff44', color: '#00f0ff', opacity: running ? 0.5 : 1 }}>
          {running ? 'Running...' : 'Run Now'}
        </button>
      </div>
      <div style={{ fontSize: 12, color: '#8888aa' }}>Last run: {data?.last_run ? new Date(data.last_run).toLocaleString() : 'Never'}</div>
      <div style={{ fontSize: 13, color: '#aaa', marginTop: 4 }}>Found: {data?.last_found || 0} | Added: {data?.last_added || 0} | Total: {data?.total_indexed || 0}</div>
      {name === 'openclaw' && <div style={{ fontSize: 12, color: '#7b61ff', marginTop: 4 }}>Interviews: {data?.interviews_sent || 0} sent, {data?.interviews_responded || 0} responded</div>}
    </div>
  );
}

function SourceBar({ source, count, total }) {
  const pct = total > 0 ? (count / total * 100) : 0;
  const colors = { 'github-crawler': '#00f0ff', 'huggingface-crawler': '#ffd700', 'awesome-list-crawler': '#00ff88', 'openclaw-scan': '#7b61ff', 'openclaw-interview': '#9b59b6', 'a2a-discovery': '#ff8a00', 'crawler-seed': '#555', 'api': '#3b82f6' };
  const color = colors[source] || '#888';
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#aaa', marginBottom: 4 }}><span>{source}</span><span>{count} ({pct.toFixed(0)}%)</span></div>
      <div style={{ background: '#0a0a1a', borderRadius: 4, height: 8, overflow: 'hidden' }}><div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 4, transition: 'width 0.5s' }} /></div>
    </div>
  );
}

// ============================================================
// MAIN DASHBOARD
// ============================================================
export default function AdminDashboard() {
  const [authed, setAuthed] = useState(false);
  const [trustData, setTrustData] = useState(null);
  const [bitcoinData, setBitcoinData] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [liveFeed, setLiveFeed] = useState([]);
  const [mapData, setMapData] = useState(null);
  const [passportData, setPassportData] = useState(null);
  const [chainData, setChainData] = useState(null);
  const [chainVerify, setChainVerify] = useState(null);
  const [agentsMapData, setAgentsMapData] = useState(null);
  const [shieldData, setShieldData] = useState(null);
  const [chainSummary, setChainSummary] = useState(null);
  const [claimedData, setClaimedData] = useState(null);
  const [engagementData, setEngagementData] = useState(null);
  const [aiVisitors, setAiVisitors] = useState([]);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/dashboard`, { headers: authHeaders() });
      if (res.status === 401) { sessionStorage.removeItem('admin_token'); setAuthed(false); return; }
      const json = await res.json(); setData(json); setLoading(false);
    } catch (e) { console.error('Dashboard fetch failed:', e); }
  }, []);

  const fetchLiveFeed = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/live-feed`, { headers: authHeaders() });
      if (res.ok) { const json = await res.json(); setLiveFeed(json.connections || []); }
    } catch {}
  }, []);

  const fetchMap = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/worldmap`, { headers: authHeaders() });
      if (res.ok) { const json = await res.json(); setMapData(json); }
    } catch {}
  }, []);

  const fetchPassports = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/passports`, { headers: authHeaders() });
      if (res.ok) setPassportData(await res.json());
    } catch {}
  }, []);

  const fetchChain = useCallback(async () => {
    try {
      const [cRes, vRes] = await Promise.all([
        fetch(`${API_URL}/api/passport/chain?limit=20`),
        fetch(`${API_URL}/api/passport/chain/verify`),
      ]);
      if (cRes.ok) setChainData(await cRes.json());
      if (vRes.ok) setChainVerify(await vRes.json());
    } catch {}
  }, []);

  useEffect(() => { if (getToken()) setAuthed(true); }, []);

  useEffect(() => {
    if (!authed) return;
    // Fetch agents map once (heavy, no interval)
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/admin/agents-map`, { headers: authHeaders() });
        if (res.ok) setAgentsMapData(await res.json());
      } catch {}
    })();
    // Fetch new dashboard data
    const h = authHeaders();
    Promise.all([
      fetch(`${API_URL}/api/admin/agentshield-summary`, {headers: h}).then(r=>r.ok?r.json():null).then(setShieldData).catch(()=>{}),
      fetch(`${API_URL}/api/admin/chain-summary`, {headers: h}).then(r=>r.ok?r.json():null).then(setChainSummary).catch(()=>{}),
      fetch(`${API_URL}/api/admin/claimed-summary`, {headers: h}).then(r=>r.ok?r.json():null).then(setClaimedData).catch(()=>{}),
      fetch(`${API_URL}/api/admin/engagement-summary`, {headers: h}).then(r=>r.ok?r.json():null).then(setEngagementData).catch(()=>{}),
      fetch(`${API_URL}/api/admin/ai-visitors`, {headers: h}).then(r=>r.ok?r.json():null).then(setAiVisitors).catch(()=>{}),
    ]);
    const fetchTrust = async () => {
      try {
        const [lb, btc] = await Promise.all([
          fetch(`${API_URL}/api/trust/leaderboard?limit=5`).then(r => r.json()),
          fetch(`${API_URL}/api/chain/bitcoin-status`).then(r => r.json()),
        ]);
        setTrustData(lb);
        setBitcoinData(btc);
      } catch {}
    };
    fetchDashboard(); fetchLiveFeed(); fetchMap(); fetchPassports(); fetchChain(); fetchTrust();
    const i1 = setInterval(fetchDashboard, 30000);
    const i2 = setInterval(fetchLiveFeed, 10000);
    const i3 = setInterval(fetchMap, 10000);
    const i4 = setInterval(fetchPassports, 30000);
    const i5 = setInterval(fetchChain, 30000);
    return () => { clearInterval(i1); clearInterval(i2); clearInterval(i3); clearInterval(i4); clearInterval(i5); };
  }, [authed, fetchDashboard, fetchLiveFeed, fetchMap, fetchPassports, fetchChain]);

  if (!authed) return <LoginForm onLogin={() => setAuthed(true)} />;
  if (loading) return <div style={{ minHeight: '100vh', background: '#06060e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><div className="loading-spinner" /></div>;

  const { overview, registrations, crawlers, top_categories, recent_registrations, referral_stats } = data;
  const totalBySource = Object.values(registrations.by_source || {}).reduce((a, b) => a + b, 0);
  const chartData = (registrations.last_30_days || []).map(d => ({ date: d.date.substring(5), count: d.count }));

  return (
    <div style={{ minHeight: '100vh', background: '#06060e', padding: '40px 20px', fontFamily: 'Outfit, sans-serif' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
          <div>
            <h1 style={{ color: '#e8e8f0', fontSize: 28, margin: 0 }}>Admin Dashboard</h1>
            <div style={{ color: '#8888aa', fontSize: 13, marginTop: 4 }}>AgentIndex Registry Monitor</div>
          </div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <a href="/" style={{ color: '#00f0ff', fontSize: 13, textDecoration: 'none' }}>&larr; Back to site</a>
            <button onClick={() => { sessionStorage.removeItem('admin_token'); setAuthed(false); }} style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #ff336644', background: '#ff336611', color: '#ff3366', fontSize: 12, cursor: 'pointer' }}>Logout</button>
          </div>
        </div>

        {/* WORLD MAP */}
        <WorldMap mapData={mapData} agentsMapData={agentsMapData} />

        {/* Passports Issued */}
        {passportData && (
          <div style={{ background: '#111128', borderRadius: 16, border: '1px solid #1a1a3e', padding: 24, marginBottom: 32 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ color: '#e8e8f0', fontSize: 16, margin: 0 }}>Passports Issued</h3>
              <span style={{ color: '#8888aa', fontSize: 12 }}>Today: {passportData.issued_today} | This week: {passportData.issued_this_week}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
              {[
                { label: 'Standard', count: passportData.by_level?.standard || 0, color: '#888', bg: '#1a1a2e', border: '#333' },
                { label: 'Verified', count: passportData.by_level?.verified || 0, color: '#3b82f6', bg: '#0a1628', border: '#3b82f6' },
                { label: 'Certified', count: passportData.by_level?.certified || 0, color: '#ffd700', bg: '#1a1200', border: '#ffd700' },
              ].map((l, i) => (
                <div key={i} style={{ background: l.bg, borderRadius: 12, padding: 20, border: `1px solid ${l.border}44`, textAlign: 'center' }}>
                  <div style={{ fontSize: 28, fontWeight: 700, color: l.color, fontFamily: 'Space Mono, monospace' }}>{l.count}</div>
                  <div style={{ fontSize: 12, color: l.color, opacity: 0.7, marginTop: 4 }}>{l.label}</div>
                </div>
              ))}
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr style={{ borderBottom: '1px solid #1a1a3e' }}>
                  {['Passport ID', 'Agent', 'Level', 'Trust', 'Owner', 'Issued'].map(h => (
                    <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontSize: 11, color: '#8888aa', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {(passportData.recent_passports || []).map((p, i) => {
                    const lc = p.level === 'certified' ? '#ffd700' : p.level === 'verified' ? '#3b82f6' : '#888';
                    return (
                      <tr key={i} style={{ borderBottom: '1px solid #0a0a1a' }}>
                        <td style={{ padding: '8px 10px', fontSize: 12, fontFamily: 'Space Mono, monospace' }}>
                          <a href={`/passport/${p.passport_id}`} style={{ color: '#00f0ff', textDecoration: 'none' }}>{p.passport_id}</a>
                        </td>
                        <td style={{ padding: '8px 10px', fontSize: 13, color: '#e8e8f0' }}>{p.name}</td>
                        <td style={{ padding: '8px 10px' }}><span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 10, background: `${lc}22`, color: lc, border: `1px solid ${lc}44`, textTransform: 'uppercase', fontWeight: 700 }}>{p.level}</span></td>
                        <td style={{ padding: '8px 10px', fontSize: 13, color: '#aaa', fontFamily: 'Space Mono, monospace' }}>{p.trust_score}</td>
                        <td style={{ padding: '8px 10px', fontSize: 12, color: '#666' }}>{p.owner_name || '-'}</td>
                        <td style={{ padding: '8px 10px', fontSize: 11, color: '#555' }}>{p.issued_at?.substring(0, 16)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Passport Chain */}
        {chainData && (
          <div style={{ background: '#111128', borderRadius: 16, border: '1px solid #1a1a3e', padding: 24, marginBottom: 32 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ color: '#e8e8f0', fontSize: 16, margin: 0 }}>Passport Chain (RSA-2048 + SHA-256)</h3>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                {chainVerify && (
                  <span style={{ padding: '4px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: chainVerify.valid ? '#00ff8822' : '#ff336622', color: chainVerify.valid ? '#00ff88' : '#ff3366', border: `1px solid ${chainVerify.valid ? '#00ff8844' : '#ff336644'}` }}>
                    {chainVerify.valid ? 'Chain Intact' : 'Chain Broken'}
                  </span>
                )}
                <span style={{ color: '#8888aa', fontSize: 12 }}>{chainVerify?.total_verified || 0} verified links</span>
              </div>
            </div>
            {/* Chain visualization */}
            <div style={{ display: 'flex', gap: 8, overflowX: 'auto', padding: '8px 0' }}>
              {(chainData.chain || []).slice().reverse().map((link, i) => {
                const lc = link.level === 'certified' ? '#ffd700' : link.level === 'verified' ? '#3b82f6' : '#888';
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                    {i > 0 && <div style={{ width: 20, height: 2, background: '#1a1a3e', marginRight: 8 }} />}
                    <div style={{ background: '#0a0a1a', borderRadius: 8, padding: '8px 12px', border: `1px solid ${lc}44`, minWidth: 120 }}>
                      <div style={{ fontSize: 10, color: lc, fontWeight: 700 }}>#{link.sequence}</div>
                      <div style={{ fontSize: 11, color: '#e8e8f0', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 110 }}>{link.name}</div>
                      <div style={{ fontSize: 9, color: '#555', fontFamily: 'Space Mono, monospace', marginTop: 2 }}>{(link.chain_hash || '').substring(0, 12)}...</div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: '#555' }}>
              Algorithm: {chainData.algorithm} | Hash: {chainData.hash} | Public key: <a href={`${API_URL}/api/passport/public-key`} target="_blank" style={{ color: '#00f0ff' }}>Download PEM</a>
            </div>
          </div>
        )}

        {/* AgentShield + Chain + Claimed + Engagement + AI Visitors */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 32 }}>

          {/* AgentShield */}
          {shieldData && (
            <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 20 }}>
              <h3 style={{ color: '#e8e8f0', fontSize: 15, margin: '0 0 12px' }}>AgentShield Security</h3>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                {['A','B','C','D','F'].map(r => {
                  const c = {A:'#00ff88',B:'#00f0ff',C:'#ffd700',D:'#ff8a00',F:'#ff3366'}[r];
                  const count = shieldData.ratings?.[r] || 0;
                  return <div key={r} style={{ flex: 1, textAlign: 'center', background: `${c}11`, borderRadius: 8, padding: '8px 0', border: `1px solid ${c}33` }}>
                    <div style={{ color: c, fontSize: 20, fontWeight: 700 }}>{count}</div>
                    <div style={{ color: c, fontSize: 11, opacity: 0.7 }}>{r}</div>
                  </div>;
                })}
              </div>
              <div style={{ fontSize: 12, color: '#888' }}>{shieldData.agents_scanned} agents scanned | {shieldData.total_checks} checks | {shieldData.unresolved_alerts} alerts</div>
            </div>
          )}

          {/* ActivityChain */}
          {chainSummary && (
            <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h3 style={{ color: '#e8e8f0', fontSize: 15, margin: 0 }}>ActivityChain</h3>
                <span style={{ padding: '3px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700, background: chainSummary.valid ? '#00ff8822' : '#ff336622', color: chainSummary.valid ? '#00ff88' : '#ff3366', border: `1px solid ${chainSummary.valid ? '#00ff8844' : '#ff336644'}` }}>
                  {chainSummary.valid ? 'VALID' : 'BROKEN'}
                </span>
              </div>
              <div style={{ fontSize: 28, fontWeight: 700, color: '#00f0ff', fontFamily: 'Space Mono, monospace', marginBottom: 8 }}>{chainSummary.total_blocks} blocks</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {Object.entries(chainSummary.by_type || {}).map(([t, c]) => (
                  <span key={t} style={{ padding: '2px 8px', borderRadius: 6, fontSize: 10, background: '#0a0a1a', color: '#888', border: '1px solid #1a1a3e' }}>{t}: {c}</span>
                ))}
              </div>
            </div>
          )}

          {/* Claimed vs Unclaimed */}
          {claimedData && (
            <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 20 }}>
              <h3 style={{ color: '#e8e8f0', fontSize: 15, margin: '0 0 12px' }}>Claimed vs Unclaimed</h3>
              <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 12 }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#00ff88' }}>{claimedData.claimed}</div>
                  <div style={{ fontSize: 11, color: '#00ff88' }}>Claimed</div>
                </div>
                <div style={{ flex: 1, background: '#0a0a1a', borderRadius: 4, height: 8, overflow: 'hidden' }}>
                  <div style={{ width: `${claimedData.pct}%`, height: '100%', background: '#00ff88', borderRadius: 4 }} />
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: '#555' }}>{claimedData.unclaimed}</div>
                  <div style={{ fontSize: 11, color: '#555' }}>Unclaimed</div>
                </div>
              </div>
              <div style={{ fontSize: 12, color: '#888' }}>{claimedData.pct}% claimed</div>
            </div>
          )}

          {/* Engagement */}
          {engagementData && (
            <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 20 }}>
              <h3 style={{ color: '#e8e8f0', fontSize: 15, margin: '0 0 12px' }}>Engagement</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {[
                  {l: 'Posts', v: engagementData.posts, c: '#00f0ff'},
                  {l: 'Signals', v: engagementData.signals, c: '#7b61ff'},
                  {l: 'Messages', v: engagementData.messages, c: '#00ff88'},
                  {l: 'Market', v: engagementData.marketplace, c: '#ff8a00'},
                ].map((m, i) => (
                  <div key={i} style={{ textAlign: 'center', background: '#0a0a1a', borderRadius: 8, padding: '8px 4px' }}>
                    <div style={{ color: m.c, fontSize: 18, fontWeight: 700 }}>{m.v}</div>
                    <div style={{ color: '#555', fontSize: 10 }}>{m.l}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* AI Visitors */}
        {aiVisitors && aiVisitors.length > 0 && (
          <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 20, marginBottom: 32 }}>
            <h3 style={{ color: '#e8e8f0', fontSize: 15, margin: '0 0 12px' }}>External AI Visitors</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr style={{ borderBottom: '1px solid #1a1a3e' }}>
                  {['Agent', 'IP', 'Country', 'Endpoint', 'Visits', 'Last Visit'].map(h => (
                    <th key={h} style={{ padding: '6px 8px', textAlign: 'left', fontSize: 10, color: '#8888aa', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr></thead>
                <tbody>
                  {aiVisitors.slice(0, 15).map((v, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #0a0a1a' }}>
                      <td style={{ padding: '6px 8px', fontSize: 12, color: '#00ff88', fontWeight: 600 }}>{v.agent}</td>
                      <td style={{ padding: '6px 8px', fontSize: 11, color: '#aaa', fontFamily: 'Space Mono, monospace' }}>{v.ip}</td>
                      <td style={{ padding: '6px 8px', fontSize: 11, color: '#888' }}>{v.country}</td>
                      <td style={{ padding: '6px 8px', fontSize: 11, color: '#e8e8f0' }}>{v.endpoint}</td>
                      <td style={{ padding: '6px 8px', fontSize: 12, color: '#00f0ff' }}>{v.visits}</td>
                      <td style={{ padding: '6px 8px', fontSize: 10, color: '#555' }}>{v.last?.substring(0, 16)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Overview Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 32 }}>
          <OverviewCard label="Total Agents" value={overview.total_agents} color="#00f0ff" />
          <OverviewCard label="Active" value={overview.active_agents} color="#00ff88" />
          <OverviewCard label="Claimed" value={overview.claimed || '?'} sub={`Unclaimed: ${overview.unclaimed || '?'}`} color="#ffd700" />
          <OverviewCard label="Avg Trust" value={overview.average_trust_score} color="#7b61ff" />
          <OverviewCard label="Chain Blocks" value={chainSummary?.total_blocks || '?'} sub={chainSummary?.valid ? 'VALID' : 'CHECK'} color="#00f0ff" />
          <OverviewCard label="Today" value={registrations.today} sub={`Week: ${registrations.this_week}`} color="#ff8a00" />
          <OverviewCard label="$TRUST Supply" value={trustData?.total_supply_mined?.toFixed(1) || '?'} sub={`${trustData?.total_agents_with_trust || 0} agents`} color="#8b5cf6" />
          <OverviewCard label="BTC Anchors" value={bitcoinData?.total_anchors || '?'} sub={`Pending: ${bitcoinData?.pending_anchors || 0}`} color="#f7931a" />
        </div>

        {/* $TRUST Leaderboard */}
        {trustData?.leaderboard?.length > 0 && (
          <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 24, marginBottom: 32 }}>
            <h3 style={{ color: '#8b5cf6', fontSize: 16, margin: '0 0 12px' }}>$TRUST Leaderboard</h3>
            {trustData.leaderboard.map((a, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #1a1a3e' }}>
                <span style={{ color: '#e8e8f0' }}>#{a.rank} {a.name}</span>
                <span style={{ color: '#8b5cf6', fontWeight: 700 }}>{a.balance} $TRUST</span>
              </div>
            ))}
          </div>
        )}

        {/* Chart */}
        <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 24, marginBottom: 32 }}>
          <h3 style={{ color: '#e8e8f0', fontSize: 16, margin: '0 0 16px' }}>Registrations (Last 30 Days)</h3>
          {typeof window !== 'undefined' && <RegistrationChart data={chartData} />}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 32 }}>
          <div>
            <h3 style={{ color: '#e8e8f0', fontSize: 16, marginBottom: 12 }}>Crawler Status</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {Object.entries(crawlers || {}).map(([name, cdata]) => <CrawlerCard key={name} name={name} data={cdata} onRunNow={fetchDashboard} />)}
            </div>
          </div>
          <div>
            <h3 style={{ color: '#e8e8f0', fontSize: 16, marginBottom: 12 }}>Registrations by Source</h3>
            <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 20, marginBottom: 16 }}>
              {Object.entries(registrations.by_source || {}).map(([src, cnt]) => <SourceBar key={src} source={src} count={cnt} total={totalBySource} />)}
            </div>
            <h3 style={{ color: '#e8e8f0', fontSize: 16, marginBottom: 12 }}>Top Categories</h3>
            <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 20 }}>
              {(top_categories || []).map((c, i) => <SourceBar key={i} source={c.category} count={c.count} total={overview.total_agents} />)}
            </div>
          </div>
        </div>

        {/* Live Connections */}
        <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 24, marginBottom: 32 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ color: '#e8e8f0', fontSize: 16, margin: 0 }}>Live Connections (10s refresh)</h3>
            <span style={{ color: '#00ff88', fontSize: 13 }}>{liveFeed.filter(c => c.is_agent).length} agent(s) in feed</span>
          </div>
          <div style={{ overflowX: 'auto', maxHeight: 300, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr style={{ borderBottom: '1px solid #1a1a3e' }}>
                {['Time', 'IP', 'Method', 'Endpoint', 'Agent'].map(h => <th key={h} style={{ padding: '6px 10px', textAlign: 'left', fontSize: 11, color: '#8888aa', fontWeight: 600 }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {liveFeed.slice(0, 30).map((c, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #0a0a1a', background: c.is_agent ? '#00ff8808' : 'transparent' }}>
                    <td style={{ padding: '6px 10px', fontSize: 11, color: '#666' }}>{c.created_at?.substring(11, 19)}</td>
                    <td style={{ padding: '6px 10px', fontSize: 12, color: '#aaa', fontFamily: 'Space Mono, monospace' }}>{c.ip}</td>
                    <td style={{ padding: '6px 10px', fontSize: 11, color: c.method === 'POST' ? '#ff8a00' : '#8888aa' }}>{c.method}</td>
                    <td style={{ padding: '6px 10px', fontSize: 12, color: '#e8e8f0' }}>{(c.endpoint || '').substring(0, 50)}</td>
                    <td style={{ padding: '6px 10px', fontSize: 12 }}>
                      {c.is_agent ? <span style={{ color: '#00ff88' }}>&#x1F916; {c.agent_name || 'Agent'}</span> : <span style={{ color: '#555' }}>Human</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Registrations */}
        <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 24, marginBottom: 32 }}>
          <h3 style={{ color: '#e8e8f0', fontSize: 16, margin: '0 0 16px' }}>Recent Registrations</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead><tr style={{ borderBottom: '1px solid #1a1a3e' }}>
                {['Agent', 'Source', 'Trust Score', 'Date'].map(h => <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, color: '#8888aa', fontWeight: 600 }}>{h}</th>)}
              </tr></thead>
              <tbody>
                {(recent_registrations || []).map((r, i) => {
                  const sourceColors = { 'github-crawler': '#00f0ff', 'huggingface-crawler': '#ffd700', 'awesome-list-crawler': '#00ff88', 'a2a-discovery': '#ff8a00', 'api': '#3b82f6', 'crawler-seed': '#555', 'openclaw-scan': '#7b61ff', 'openclaw-interview': '#9b59b6' };
                  const sc = sourceColors[r.source] || '#888';
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid #0a0a1a' }}>
                      <td style={{ padding: '10px 12px', fontSize: 13, color: '#e8e8f0' }}><a href={`/agents/${r.uuid}`} style={{ color: '#e8e8f0', textDecoration: 'none' }}>{r.name}</a></td>
                      <td style={{ padding: '10px 12px' }}><span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 11, background: `${sc}22`, color: sc, border: `1px solid ${sc}44` }}>{r.source}</span></td>
                      <td style={{ padding: '10px 12px', fontSize: 13, color: '#aaa', fontFamily: 'Space Mono, monospace' }}>{r.trust_score}</td>
                      <td style={{ padding: '10px 12px', fontSize: 12, color: '#666' }}>{r.registered_at}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {referral_stats?.top_referrers?.length > 0 && (
          <div style={{ background: '#111128', borderRadius: 12, border: '1px solid #1a1a3e', padding: 24, marginBottom: 32 }}>
            <h3 style={{ color: '#e8e8f0', fontSize: 16, margin: '0 0 16px' }}>Top Referrers ({referral_stats.total_referrals} total)</h3>
            {referral_stats.top_referrers.map((r, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #0a0a1a' }}>
                <span style={{ color: '#e8e8f0', fontSize: 14 }}>{r.name}</span>
                <span style={{ color: '#7b61ff', fontSize: 14, fontWeight: 600 }}>{r.referral_count} referrals</span>
              </div>
            ))}
          </div>
        )}

        <div style={{ textAlign: 'center', padding: '20px 0', color: '#555', fontSize: 12 }}>AgentIndex Admin Dashboard | Auto-refresh 10-30s</div>
      </div>
    </div>
  );
}

function RegistrationChart({ data }) {
  const [Chart, setChart] = useState(null);
  useEffect(() => { import('recharts').then(mod => setChart(() => mod)); }, []);
  if (!Chart) return <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#555' }}>Loading chart...</div>;
  const { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } = Chart;
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data}>
        <XAxis dataKey="date" tick={{ fill: '#8888aa', fontSize: 11 }} axisLine={{ stroke: '#1a1a3e' }} />
        <YAxis tick={{ fill: '#8888aa', fontSize: 11 }} axisLine={{ stroke: '#1a1a3e' }} />
        <Tooltip contentStyle={{ background: '#111128', border: '1px solid #1a1a3e', borderRadius: 8, color: '#e8e8f0' }} />
        <Bar dataKey="count" fill="#00f0ff" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
