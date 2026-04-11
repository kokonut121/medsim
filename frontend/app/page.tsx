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
    <div style={{ background: "var(--midnight)", minHeight: "100vh", color: "var(--bone)" }}>

      {/* ── Nav ─────────────────────────────────────── */}
      <nav style={{
        position: "sticky", top: 0, zIndex: 100,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 40px", height: 60,
        background: "rgba(6,10,9,0.85)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid var(--bone-chalk)",
      }}>
        <div style={{ fontFamily: "var(--font-display-stack)", fontSize: 20, fontWeight: 700, letterSpacing: "-0.03em" }}>
          Med<span style={{ color: "var(--phosphor)" }}>Sentinel</span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Link href="/login" style={{
            padding: "7px 18px",
            border: "1px solid var(--bone-chalk)",
            borderRadius: 6,
            color: "var(--bone-soft)",
            textDecoration: "none",
            fontSize: 13,
            fontFamily: "var(--font-body-stack)",
          }}>
            Sign in
          </Link>
          <Link href="/signup" style={{
            padding: "7px 18px",
            background: "var(--phosphor)",
            borderRadius: 6,
            color: "#fff",
            textDecoration: "none",
            fontSize: 13,
            fontWeight: 600,
            fontFamily: "var(--font-body-stack)",
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
      }}>
        <div style={{
          display: "inline-block", marginBottom: 24,
          padding: "4px 14px",
          borderRadius: 20,
          border: "1px solid var(--phosphor)",
          color: "var(--phosphor)",
          fontSize: 11,
          fontFamily: "var(--font-mono-stack)",
          letterSpacing: "0.14em",
        }}>
          TRAUMA CENTER INTELLIGENCE
        </div>

        <h1 style={{
          margin: "0 0 24px",
          fontFamily: "var(--font-display-stack)",
          fontSize: "clamp(40px, 7vw, 68px)",
          fontWeight: 700,
          lineHeight: 1.08,
          letterSpacing: "-0.04em",
          color: "var(--bone)",
        }}>
          Your facility,<br />
          <span style={{ color: "var(--phosphor)" }}>seen clearly.</span>
        </h1>

        <p style={{
          margin: "0 0 40px",
          fontSize: "clamp(15px, 2.5vw, 18px)",
          lineHeight: 1.65,
          color: "var(--bone-soft)",
          maxWidth: 560,
        }}>
          MedSentinel reconstructs your trauma center in 3D, deploys AI safety agent teams
          across the model, and surfaces critical findings before they become incidents.
        </p>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
          <Link href="/signup" style={{
            padding: "14px 32px",
            background: "var(--phosphor)",
            color: "#fff",
            borderRadius: 7,
            textDecoration: "none",
            fontSize: 15,
            fontWeight: 600,
            fontFamily: "var(--font-body-stack)",
          }}>
            Get started →
          </Link>
          <Link href="/viewer" style={{
            padding: "14px 32px",
            border: "1px solid var(--bone-chalk)",
            color: "var(--bone-soft)",
            borderRadius: 7,
            textDecoration: "none",
            fontSize: 15,
            fontFamily: "var(--font-body-stack)",
          }}>
            See live demo
          </Link>
        </div>
      </section>

      {/* ── Features ────────────────────────────────── */}
      <section style={{ padding: "80px 24px", maxWidth: 1040, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <p style={{ fontFamily: "var(--font-mono-stack)", fontSize: 11, letterSpacing: "0.16em", color: "var(--phosphor)", marginBottom: 12 }}>
            CAPABILITIES
          </p>
          <h2 style={{ fontFamily: "var(--font-display-stack)", fontSize: "clamp(28px, 4vw, 40px)", fontWeight: 700, letterSpacing: "-0.03em", margin: 0 }}>
            Everything your safety team needs
          </h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 20 }}>
          {FEATURES.map((f) => (
            <div key={f.title} style={{
              padding: "28px 24px",
              background: "var(--midnight-card)",
              border: "1px solid var(--bone-chalk)",
              borderRadius: 10,
            }}>
              <div style={{ fontSize: 22, marginBottom: 14, color: "var(--phosphor)" }}>{f.icon}</div>
              <h3 style={{ margin: "0 0 10px", fontFamily: "var(--font-display-stack)", fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em" }}>
                {f.title}
              </h3>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "var(--bone-soft)" }}>
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ────────────────────────────── */}
      <section style={{
        padding: "80px 24px",
        maxWidth: 800, margin: "0 auto",
        borderTop: "1px solid var(--bone-chalk)",
      }}>
        <div style={{ textAlign: "center", marginBottom: 56 }}>
          <p style={{ fontFamily: "var(--font-mono-stack)", fontSize: 11, letterSpacing: "0.16em", color: "var(--phosphor)", marginBottom: 12 }}>
            HOW IT WORKS
          </p>
          <h2 style={{ fontFamily: "var(--font-display-stack)", fontSize: "clamp(28px, 4vw, 40px)", fontWeight: 700, letterSpacing: "-0.03em", margin: 0 }}>
            From footage to findings in four steps
          </h2>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          {STEPS.map((s, i) => (
            <div key={s.n} style={{
              display: "grid",
              gridTemplateColumns: "56px 1fr",
              gap: "0 24px",
              padding: "28px 0",
              borderBottom: i < STEPS.length - 1 ? "1px solid var(--bone-chalk)" : "none",
            }}>
              <div style={{
                fontFamily: "var(--font-mono-stack)",
                fontSize: 13,
                fontWeight: 700,
                color: "var(--phosphor)",
                paddingTop: 3,
              }}>
                {s.n}
              </div>
              <div>
                <h3 style={{ margin: "0 0 6px", fontFamily: "var(--font-display-stack)", fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em" }}>
                  {s.title}
                </h3>
                <p style={{ margin: 0, fontSize: 14, lineHeight: 1.65, color: "var(--bone-soft)" }}>
                  {s.body}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────── */}
      <section style={{
        padding: "80px 24px 100px",
        textAlign: "center",
        borderTop: "1px solid var(--bone-chalk)",
      }}>
        <h2 style={{
          fontFamily: "var(--font-display-stack)",
          fontSize: "clamp(28px, 4vw, 44px)",
          fontWeight: 700,
          letterSpacing: "-0.04em",
          margin: "0 0 16px",
        }}>
          Ready to deploy MedSentinel?
        </h2>
        <p style={{ fontSize: 16, color: "var(--bone-soft)", margin: "0 0 36px" }}>
          Join trauma centers using AI to stay ahead of safety incidents.
        </p>
        <Link href="/signup" style={{
          display: "inline-block",
          padding: "14px 40px",
          background: "var(--phosphor)",
          color: "#fff",
          borderRadius: 7,
          textDecoration: "none",
          fontSize: 15,
          fontWeight: 600,
          fontFamily: "var(--font-body-stack)",
        }}>
          Request access →
        </Link>
      </section>

      {/* ── Footer ──────────────────────────────────── */}
      <footer style={{
        borderTop: "1px solid var(--bone-chalk)",
        padding: "24px 40px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 12,
      }}>
        <div style={{ fontFamily: "var(--font-display-stack)", fontSize: 16, fontWeight: 700, letterSpacing: "-0.03em" }}>
          Med<span style={{ color: "var(--phosphor)" }}>Sentinel</span>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: "var(--bone-soft)", fontFamily: "var(--font-mono-stack)" }}>
          © 2025 MedSentinel. Trauma center intelligence.
        </p>
      </footer>

    </div>
  );
}
