import Link from "next/link";

const FEATURES = [
  {
    icon: "⬡",
    title: "3D World Reconstruction",
    body: "Upload facility imagery and generate a photorealistic Gaussian splat world model of your trauma center in minutes.",
  },
  {
    icon: "◈",
    title: "AI Safety Agent Teams",
    body: "Six specialized domain agents — infection control, fall risk, medication safety, and more — sweep the model in parallel and surface grounded findings.",
  },
  {
    icon: "◎",
    title: "Scenario Simulation",
    body: "Swarm multi-role agent teams through crisis scenarios and receive a distilled tactical best-plan before the real thing.",
  },
  {
    icon: "▦",
    title: "Compliance Reports",
    body: "Export findings as structured PDF reports or machine-readable manifests for your accreditation and quality teams.",
  },
];

const STEPS = [
  { n: "01", title: "Upload imagery",       body: "Drop street-view, drone, or walkthrough footage of your facility." },
  { n: "02", title: "Generate world model", body: "Our pipeline builds a navigable 3D splat reconstruction tied to a semantic scene graph." },
  { n: "03", title: "Deploy agent teams",   body: "AI agents patrol the model, cross-reference spatial data, and flag safety issues." },
  { n: "04", title: "Act on findings",      body: "Review annotated findings, run simulations, and download compliance-ready reports." },
];

export default function LandingPage() {
  return (
    <div style={{ background: "var(--paper)", minHeight: "100vh", color: "var(--ink)" }}>

      {/* ── Nav ─────────────────────────────────────── */}
      <nav style={{
        position: "sticky", top: 0, zIndex: 100,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 40px", height: 60,
        background: "rgba(241,235,221,0.92)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--chalk-hard)",
      }}>
        <div style={{ fontFamily: "var(--font-display-stack)", fontSize: 20, fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink)" }}>
          Med<span style={{ color: "var(--signal)" }}>Sentinel</span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Link href="/login" style={{
            padding: "7px 18px",
            border: "1px solid var(--chalk-hard)",
            borderRadius: 2,
            color: "var(--mercury)",
            textDecoration: "none",
            fontSize: 12,
            fontFamily: "var(--font-mono-stack)",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}>
            Sign in
          </Link>
          <Link href="/signup" style={{
            padding: "7px 18px",
            background: "var(--ink)",
            borderRadius: 2,
            color: "var(--paper-hi)",
            textDecoration: "none",
            fontSize: 12,
            fontFamily: "var(--font-mono-stack)",
            fontWeight: 600,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}>
            Request access
          </Link>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────── */}
      <section style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        textAlign: "center",
        padding: "100px 24px 80px",
        maxWidth: 760, margin: "0 auto",
        borderBottom: "1px solid var(--chalk-hard)",
      }}>
        <div style={{
          display: "inline-block", marginBottom: 24,
          padding: "4px 14px",
          border: "1px solid var(--chalk-hard)",
          color: "var(--mercury)",
          fontSize: 10,
          fontFamily: "var(--font-mono-stack)",
          letterSpacing: "0.22em",
          textTransform: "uppercase",
        }}>
          Trauma Center Intelligence
        </div>

        <h1 style={{
          margin: "0 0 24px",
          fontFamily: "var(--font-display-stack)",
          fontSize: "clamp(40px, 7vw, 72px)",
          fontWeight: 300,
          lineHeight: 0.92,
          letterSpacing: "-0.04em",
          color: "var(--ink)",
          fontVariationSettings: '"opsz" 144',
        }}>
          Your facility,<br />
          <em style={{ fontStyle: "italic", color: "var(--signal)" }}>seen clearly.</em>
        </h1>

        <p style={{
          margin: "0 0 40px",
          fontSize: "clamp(15px, 2vw, 17px)",
          lineHeight: 1.7,
          color: "var(--mercury)",
          maxWidth: 520,
          fontFamily: "var(--font-body-stack)",
        }}>
          MedSentinel reconstructs your trauma center in 3D, deploys AI safety agent teams
          across the model, and surfaces critical findings before they become incidents.
        </p>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
          <Link href="/signup" style={{
            padding: "14px 28px 14px 32px",
            background: "var(--ink)",
            color: "var(--paper-hi)",
            borderRadius: 2,
            textDecoration: "none",
            fontSize: 11,
            fontWeight: 600,
            fontFamily: "var(--font-mono-stack)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}>
            Get started →
          </Link>
          <Link href="/viewer" style={{
            padding: "14px 28px 14px 32px",
            border: "1px solid var(--chalk-hard)",
            color: "var(--mercury)",
            borderRadius: 2,
            textDecoration: "none",
            fontSize: 11,
            fontFamily: "var(--font-mono-stack)",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}>
            Live demo →
          </Link>
        </div>
      </section>

      {/* ── Features ────────────────────────────────── */}
      <section style={{ padding: "80px 24px", maxWidth: 1040, margin: "0 auto", borderBottom: "1px solid var(--chalk-hard)" }}>
        <p style={{ fontFamily: "var(--font-mono-stack)", fontSize: 10, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--mercury)", marginBottom: 48, textAlign: "center" }}>
          Capabilities
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 24 }}>
          {FEATURES.map((f) => (
            <div key={f.title} style={{
              padding: "28px 24px",
              background: "var(--paper-hi)",
              border: "1px solid var(--chalk-hard)",
              borderRadius: 2,
              boxShadow: "5px 5px 0 var(--ink)",
            }}>
              <div style={{ fontSize: 20, marginBottom: 14, color: "var(--signal)" }}>{f.icon}</div>
              <h3 style={{ margin: "0 0 10px", fontFamily: "var(--font-display-stack)", fontSize: 18, fontWeight: 400, color: "var(--ink)" }}>
                {f.title}
              </h3>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--mercury)", fontFamily: "var(--font-body-stack)" }}>
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ────────────────────────────── */}
      <section style={{ padding: "80px 24px", maxWidth: 760, margin: "0 auto", borderBottom: "1px solid var(--chalk-hard)" }}>
        <p style={{ fontFamily: "var(--font-mono-stack)", fontSize: 10, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--mercury)", marginBottom: 48, textAlign: "center" }}>
          How it works
        </p>
        {STEPS.map((s, i) => (
          <div key={s.n} style={{
            display: "grid", gridTemplateColumns: "56px 1fr", gap: "0 24px",
            padding: "28px 0",
            borderBottom: i < STEPS.length - 1 ? "1px solid var(--chalk)" : "none",
          }}>
            <div style={{ fontFamily: "var(--font-mono-stack)", fontSize: 12, fontWeight: 700, color: "var(--signal)", paddingTop: 3 }}>
              {s.n}
            </div>
            <div>
              <h3 style={{ margin: "0 0 6px", fontFamily: "var(--font-display-stack)", fontSize: 20, fontWeight: 400, color: "var(--ink)" }}>
                {s.title}
              </h3>
              <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: "var(--mercury)", fontFamily: "var(--font-body-stack)" }}>
                {s.body}
              </p>
            </div>
          </div>
        ))}
      </section>

      {/* ── CTA ─────────────────────────────────────── */}
      <section style={{ padding: "80px 24px 100px", textAlign: "center", maxWidth: 600, margin: "0 auto" }}>
        <h2 style={{ fontFamily: "var(--font-display-stack)", fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 300, letterSpacing: "-0.04em", margin: "0 0 16px", color: "var(--ink)" }}>
          Ready to deploy MedSentinel?
        </h2>
        <p style={{ fontSize: 15, color: "var(--mercury)", margin: "0 0 36px", fontFamily: "var(--font-body-stack)" }}>
          Join trauma centers using AI to stay ahead of safety incidents.
        </p>
        <Link href="/signup" style={{
          display: "inline-block",
          padding: "14px 36px",
          background: "var(--ink)",
          color: "var(--paper-hi)",
          borderRadius: 2,
          textDecoration: "none",
          fontSize: 11,
          fontWeight: 600,
          fontFamily: "var(--font-mono-stack)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
        }}>
          Request access →
        </Link>
      </section>

      {/* ── Footer ──────────────────────────────────── */}
      <footer style={{
        borderTop: "1px solid var(--chalk-hard)",
        padding: "24px 40px",
        display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12,
      }}>
        <div style={{ fontFamily: "var(--font-display-stack)", fontSize: 16, fontWeight: 700, letterSpacing: "-0.03em", color: "var(--ink)" }}>
          Med<span style={{ color: "var(--signal)" }}>Sentinel</span>
        </div>
        <p style={{ margin: 0, fontSize: 11, color: "var(--mercury)", fontFamily: "var(--font-mono-stack)", letterSpacing: "0.1em" }}>
          © 2025 MEDSENTINEL · TRAUMA CENTER INTELLIGENCE
        </p>
      </footer>
    </div>
  );
}
