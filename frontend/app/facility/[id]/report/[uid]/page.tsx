import type { Route } from "next";

import { BackLink } from "@/components/ui/BackLink";
import { buildApiUrl } from "@/lib/runtime";
import type { Finding } from "@/types";

const SEV_COLOR: Record<string, string> = {
  CRITICAL: "var(--signal)",
  HIGH:     "var(--ember)",
  ADVISORY: "var(--phosphor)",
};

const DOMAIN_COLOR: Record<string, string> = {
  ICA: "#e74c3c", ERA: "#e74c3c",
  MSA: "#e67e22", FRA: "#e67e22",
  PFA: "#2dc7a0", SCA: "#3a3a9e",
};

const DOMAIN_LABEL: Record<string, string> = {
  ICA: "Infection Control",
  ERA: "Emergency Response",
  MSA: "Medication Safety",
  FRA: "Fall Risk",
  PFA: "Patient Flow",
  SCA: "Safe Communication",
};

async function getFindings(unitId: string): Promise<{ scan_id: string; findings: Finding[] } | null> {
  try {
    const res = await fetch(buildApiUrl(`/api/reports/${unitId}/manifest`), { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function SevBadge({ sev }: { sev: string }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 8px",
      borderRadius: 3,
      fontSize: 10,
      fontFamily: "var(--font-mono-stack)",
      fontWeight: 700,
      letterSpacing: "0.1em",
      background: SEV_COLOR[sev] ?? "var(--mercury)",
      color: "#fff",
    }}>
      {sev}
    </span>
  );
}

function FindingRow({ f, i }: { f: Finding; i: number }) {
  const domainColor = DOMAIN_COLOR[f.domain] ?? "var(--mercury)";
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "28px 1fr",
      gap: "0 16px",
      padding: "18px 0",
      borderBottom: "1px solid var(--chalk)",
    }}>
      {/* index */}
      <div style={{ paddingTop: 2, fontFamily: "var(--font-mono-stack)", fontSize: 11, color: "var(--mercury-hi)", textAlign: "right" }}>
        {String(i + 1).padStart(2, "0")}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {/* header row */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <SevBadge sev={f.severity} />
          <span style={{
            display: "inline-block",
            padding: "2px 8px",
            borderRadius: 3,
            fontSize: 10,
            fontFamily: "var(--font-mono-stack)",
            fontWeight: 600,
            letterSpacing: "0.08em",
            background: domainColor + "22",
            color: domainColor,
            border: `1px solid ${domainColor}44`,
          }}>
            {DOMAIN_LABEL[f.domain] ?? f.domain}
          </span>
          <span style={{ fontFamily: "var(--font-mono-stack)", fontSize: 11, color: "var(--mercury-hi)" }}>
            {f.room_id}
          </span>
          <span style={{ fontFamily: "var(--font-mono-stack)", fontSize: 11, color: "var(--mercury-hi)", marginLeft: "auto" }}>
            {Math.round(f.confidence * 100)}% conf
          </span>
        </div>
        {/* title */}
        <p style={{ margin: 0, fontWeight: 600, fontSize: 14, color: "var(--ink)" }}>
          {f.label_text}
        </p>
        {/* recommendation */}
        <p style={{ margin: 0, fontSize: 13, color: "var(--mercury)" }}>
          → {f.recommendation}
        </p>
        {/* compound domains */}
        {f.compound_domains && f.compound_domains.length > 1 && (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {f.compound_domains.map((d) => (
              <span key={d} style={{
                fontSize: 10,
                fontFamily: "var(--font-mono-stack)",
                padding: "1px 5px",
                borderRadius: 2,
                background: "var(--chalk-soft)",
                color: "var(--mercury)",
              }}>{d}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string; uid: string }>;
}) {
  const { id, uid } = await params;
  const data = await getFindings(uid);

  const findings = data?.findings ?? [];
  const critical = findings.filter((f) => f.severity === "CRITICAL");
  const high      = findings.filter((f) => f.severity === "HIGH");
  const advisory  = findings.filter((f) => f.severity === "ADVISORY");

  const byDomain = findings.reduce<Record<string, Finding[]>>((acc, f) => {
    (acc[f.domain] ??= []).push(f);
    return acc;
  }, {});

  return (
    <main className="shell">
      <BackLink href={`/facility/${id}` as Route} label="Hub" />

      {/* header */}
      <div className="panel" style={{ marginBottom: 24 }}>
        <div className="eyebrow">Safety scan · {uid}</div>
        <h1 className="page-title">Findings report</h1>
        {data?.scan_id && (
          <p className="muted" style={{ fontFamily: "var(--font-mono-stack)", fontSize: 12 }}>
            Scan ID: {data.scan_id}
          </p>
        )}

        {/* summary stats */}
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "20px 0 24px" }}>
          {[
            { label: "Critical", count: critical.length, color: "var(--signal)" },
            { label: "High",     count: high.length,     color: "var(--ember)"  },
            { label: "Advisory", count: advisory.length, color: "var(--phosphor)" },
          ].map(({ label, count, color }) => (
            <div key={label} style={{
              flex: "1 1 80px",
              padding: "14px 16px",
              background: "var(--chalk-soft)",
              border: "1px solid var(--chalk)",
              borderRadius: 6,
              textAlign: "center",
            }}>
              <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "var(--font-display-stack)", color }}>{count}</div>
              <div style={{ fontSize: 11, color: "var(--mercury)", fontFamily: "var(--font-mono-stack)", letterSpacing: "0.1em" }}>{label.toUpperCase()}</div>
            </div>
          ))}
          <div style={{
            flex: "1 1 80px",
            padding: "14px 16px",
            background: "var(--chalk-soft)",
            border: "1px solid var(--chalk)",
            borderRadius: 6,
            textAlign: "center",
          }}>
            <div style={{ fontSize: 28, fontWeight: 700, fontFamily: "var(--font-display-stack)", color: "var(--ink)" }}>{findings.length}</div>
            <div style={{ fontSize: 11, color: "var(--mercury)", fontFamily: "var(--font-mono-stack)", letterSpacing: "0.1em" }}>TOTAL</div>
          </div>
        </div>

        {/* domain breakdown */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
          {Object.entries(byDomain).map(([domain, fs]) => (
            <span key={domain} style={{
              padding: "4px 10px",
              borderRadius: 4,
              fontSize: 12,
              fontFamily: "var(--font-mono-stack)",
              background: (DOMAIN_COLOR[domain] ?? "#888") + "18",
              color: DOMAIN_COLOR[domain] ?? "var(--mercury)",
              border: `1px solid ${(DOMAIN_COLOR[domain] ?? "#888")}33`,
            }}>
              {DOMAIN_LABEL[domain] ?? domain} · {fs.length}
            </span>
          ))}
        </div>

        {/* export buttons */}
        <div className="cta-row">
          <a className="button" href={buildApiUrl(`/api/reports/${uid}/pdf`)}>
            Download PDF
          </a>
          <a className="button secondary" href={buildApiUrl(`/api/reports/${uid}/manifest`)}>
            Raw JSON
          </a>
        </div>
      </div>

      {/* findings list */}
      {findings.length === 0 ? (
        <div className="panel">
          <p className="muted">No findings yet — run a scan first.</p>
        </div>
      ) : (
        <div className="panel">
          <div className="eyebrow" style={{ marginBottom: 4 }}>All findings</div>
          <div>
            {findings.map((f, i) => (
              <FindingRow key={f.finding_id} f={f} i={i} />
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
