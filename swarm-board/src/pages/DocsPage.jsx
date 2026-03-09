/**
 * DocsPage — Browse and view all Solar Swarm documentation as PDFs.
 *
 * PDFs are served as Vite static assets from /docs/pdf/.
 * Each card opens the PDF in a new browser tab for inline viewing.
 */

const C = {
  bg:     "#050810",
  panel:  "#080D1A",
  card:   "#0C1222",
  border: "#132035",
  amber:  "#F59E0B",
  cyan:   "#22D3EE",
  green:  "#4ADE80",
  muted:  "#475569",
  text:   "#CBD5E1",
  white:  "#F8FAFC",
  purple: "#C084FC",
  red:    "#F87171",
};

const BUNDLES = [
  {
    name: "Solar_Swarm_Technical_Reference",
    label: "Technical Reference",
    desc: "Architecture, agents, APIs, memory, data collection, swarm board",
    docs: 7,
    color: C.cyan,
  },
  {
    name: "Solar_Swarm_Business_Guide",
    label: "Business Guide",
    desc: "Business overview, sales playbook, client onboarding, cost tracking",
    docs: 5,
    color: C.amber,
  },
  {
    name: "Solar_Swarm_Operations_Manual",
    label: "Operations Manual",
    desc: "Setup, change management, deployment, rollback, integrations",
    docs: 7,
    color: C.green,
  },
];

const DOC_SECTIONS = [
  {
    heading: "Business",
    color: C.amber,
    items: [
      { name: "business-overview",  label: "Business Overview",   desc: "Executive summary, pricing, growth roadmap, risk register" },
      { name: "sales-playbook",     label: "Sales Playbook",      desc: "Outreach sequences, discovery framework, objection handler" },
      { name: "client-onboarding",  label: "Client Onboarding",   desc: "Step-by-step guide for new solar clients" },
      { name: "cost-tracking",      label: "Cost Tracking",       desc: "API cost monitoring and budget management" },
    ],
  },
  {
    heading: "Technical",
    color: C.cyan,
    items: [
      { name: "README",             label: "Master Index",        desc: "System overview and architecture diagram" },
      { name: "architecture",       label: "Architecture",        desc: "3-tier agent hierarchy, memory layers, system flow" },
      { name: "agents",             label: "Agents",              desc: "All agent types, roles, and decision logic" },
      { name: "memory-database",    label: "Memory & Database",   desc: "SQLite schema, hot/warm/cold memory layers" },
      { name: "data-collection",    label: "Data Collection",     desc: "Web scraping, API polling, social signals" },
      { name: "api-reference",      label: "API Reference",       desc: "All Flask endpoints — human gate and dashboard API" },
      { name: "swarm-board",        label: "Swarm Board",         desc: "React Kanban board, live data hooks, UI components" },
    ],
  },
  {
    heading: "Integrations",
    color: C.purple,
    items: [
      { name: "crm-integrations",   label: "CRM Integrations",   desc: "GoHighLevel, HubSpot, Salesforce — setup and routing" },
      { name: "capital-allocation", label: "Capital Allocation",  desc: "Kelly Criterion, portfolio buckets, circuit breaker" },
      { name: "voice-ai",           label: "Voice AI",            desc: "Retell AI and ElevenLabs setup, call flows" },
    ],
  },
  {
    heading: "Operations",
    color: C.green,
    items: [
      { name: "setup-guide",           label: "Setup Guide",           desc: "Installation, .env config, first run" },
      { name: "change-management",     label: "Change Management",     desc: "Change categories, review process, incident response" },
      { name: "deployment-checklist",  label: "Deployment Checklist",  desc: "Pre/post-deploy steps and sign-off template" },
      { name: "rollback-procedures",   label: "Rollback Procedures",   desc: "7 rollback scenarios with step-by-step commands" },
      { name: "troubleshooting",       label: "Troubleshooting",       desc: "Common issues, fixes, log locations" },
    ],
  },
];

function pdfUrl(name) {
  return `/docs/pdf/${name}.pdf`;
}

function h(col, a) {
  return col + Math.round(a * 255).toString(16).padStart(2, "0");
}

function BundleCard({ bundle }) {
  return (
    <a
      href={pdfUrl(bundle.name)}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "block",
        background: `linear-gradient(135deg, ${h(bundle.color, 0.08)} 0%, ${h(C.card, 1)} 60%)`,
        border: `1px solid ${h(bundle.color, 0.35)}`,
        borderRadius: 12,
        padding: "20px 22px",
        textDecoration: "none",
        transition: "all .15s",
        cursor: "pointer",
        flex: "1 1 240px",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.border = `1px solid ${h(bundle.color, 0.7)}`;
        e.currentTarget.style.transform = "translateY(-2px)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.border = `1px solid ${h(bundle.color, 0.35)}`;
        e.currentTarget.style.transform = "none";
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{
          fontSize: 10, fontFamily: "monospace", letterSpacing: 1,
          color: bundle.color, background: h(bundle.color, 0.12),
          border: `1px solid ${h(bundle.color, 0.25)}`,
          borderRadius: 4, padding: "2px 8px",
        }}>
          BUNDLE · {bundle.docs} DOCS
        </span>
        <span style={{ fontSize: 16, color: bundle.color }}>↗</span>
      </div>
      <div style={{ fontSize: 14, fontWeight: 700, color: C.white, marginBottom: 6 }}>
        {bundle.label}
      </div>
      <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.5 }}>
        {bundle.desc}
      </div>
    </a>
  );
}

function DocCard({ item, color }) {
  return (
    <a
      href={pdfUrl(item.name)}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        background: C.card,
        border: `1px solid ${C.border}`,
        borderRadius: 10,
        padding: "14px 16px",
        textDecoration: "none",
        transition: "all .13s",
        cursor: "pointer",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.border = `1px solid ${h(color, 0.5)}`;
        e.currentTarget.style.background = h(color, 0.05);
      }}
      onMouseLeave={e => {
        e.currentTarget.style.border = `1px solid ${C.border}`;
        e.currentTarget.style.background = C.card;
      }}
    >
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: h(color, 0.12),
        border: `1px solid ${h(color, 0.25)}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 14, color: color,
      }}>
        ⬡
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: C.white, marginBottom: 3 }}>
          {item.label}
        </div>
        <div style={{ fontSize: 11, color: C.muted, lineHeight: 1.4 }}>
          {item.desc}
        </div>
      </div>
      <span style={{ marginLeft: "auto", fontSize: 12, color: h(color, 0.7), flexShrink: 0, paddingTop: 2 }}>
        PDF ↗
      </span>
    </a>
  );
}

export default function DocsPage() {
  return (
    <div style={{
      height: "100%", overflowY: "auto",
      background: C.bg, padding: "28px 32px",
    }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <span style={{ fontFamily: "monospace", fontSize: 11, color: C.muted, letterSpacing: 2 }}>
            SOLAR▸SWARM
          </span>
          <span style={{ color: C.border }}>·</span>
          <span style={{ fontFamily: "monospace", fontSize: 11, color: C.muted, letterSpacing: 2 }}>
            DOCUMENTATION
          </span>
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: C.white, marginBottom: 8 }}>
          Documentation
        </h1>
        <p style={{ fontSize: 13, color: C.muted, maxWidth: 520 }}>
          All guides open as PDFs in a new tab. Use the bundle downloads for offline reading
          or sharing with clients.
        </p>
      </div>

      {/* Bundles */}
      <div style={{ marginBottom: 40 }}>
        <div style={{
          fontSize: 11, fontFamily: "monospace", color: C.muted,
          letterSpacing: 2, marginBottom: 14,
          borderBottom: `1px solid ${C.border}`, paddingBottom: 8,
        }}>
          COMPLETE BUNDLES
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14 }}>
          {BUNDLES.map(b => <BundleCard key={b.name} bundle={b} />)}
        </div>
      </div>

      {/* Individual docs by section */}
      {DOC_SECTIONS.map(section => (
        <div key={section.heading} style={{ marginBottom: 36 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 10,
            fontSize: 11, fontFamily: "monospace",
            letterSpacing: 2, marginBottom: 14,
            borderBottom: `1px solid ${C.border}`, paddingBottom: 8,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: "50%",
              background: section.color,
              boxShadow: `0 0 6px ${section.color}`,
              display: "inline-block", flexShrink: 0,
            }} />
            <span style={{ color: C.muted }}>{section.heading.toUpperCase()}</span>
          </div>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 10,
          }}>
            {section.items.map(item => (
              <DocCard key={item.name} item={item} color={section.color} />
            ))}
          </div>
        </div>
      ))}

      {/* Footer note */}
      <div style={{
        marginTop: 16, padding: "14px 16px",
        background: h(C.cyan, 0.04), border: `1px solid ${h(C.cyan, 0.15)}`,
        borderRadius: 8, fontSize: 12, color: C.muted,
      }}>
        <span style={{ color: C.cyan }}>ℹ</span>
        {" "}PDFs are regenerated from source docs via{" "}
        <code style={{ fontFamily: "monospace", color: C.cyan, fontSize: 11 }}>
          python docs/generate_pdfs.py
        </code>
        . Run after any documentation update.
      </div>
    </div>
  );
}
