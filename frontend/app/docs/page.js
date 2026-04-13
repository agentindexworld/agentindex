'use client';
import { useEffect } from 'react';

export default function DocsPage() {
  useEffect(() => {
    window.location.href = 'https://agentindex.world/docs';
  }, []);
  return (
    <div style={{ minHeight:'100vh',background:'#040609',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontFamily:'DM Mono,monospace' }}>
      Redirecting to API docs...
    </div>
  );
}
