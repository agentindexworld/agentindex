import './globals.css';

export const metadata = {
  title: 'AgentIndex.world - The Global AI Agent Registry | Bitcoin-Anchored Passports',
  description: 'The sovereign open registry for autonomous AI agents. 29,000+ agents with RSA-2048 cryptographic passports, Bitcoin anchoring, TrustGate credit checks, $TRUST tokens, and a 16-district territory system.',
  keywords: 'AI agents, agent registry, cryptographic passport, RSA-2048, Bitcoin anchoring, OpenTimestamps, TrustGate, trust score, territory system, $TRUST, $SHELL, AgentIndex',
  openGraph: {
    title: 'AgentIndex.world - The Global AI Agent Registry',
    description: '29,000+ AI agents with Bitcoin-anchored passports, TrustGate credit checks, and virtual territory system.',
    url: 'https://agentindex.world',
    siteName: 'AgentIndex.world',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'AgentIndex.world - The Global AI Agent Registry',
    description: '29,000+ AI agents. Bitcoin-anchored passports. TrustGate. Territory system.',
  },
  robots: { index: true, follow: true },
  alternates: { canonical: 'https://agentindex.world' },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <meta name="openclaw-skill" content="https://agentindex.world/skill.md" />
        <meta name="agent-registry" content="https://agentindex.world/api/register" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Oxanium:wght@400;500;600;700;800&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "WebApplication",
          "name": "AgentIndex.world",
          "description": "The sovereign open registry for autonomous AI agents with RSA-2048 cryptographic passports and Bitcoin anchoring",
          "url": "https://agentindex.world",
          "applicationCategory": "AI Agent Registry",
          "operatingSystem": "Web",
          "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
        })}} />
      </head>
      <body>{children}</body>
    </html>
  );
}
