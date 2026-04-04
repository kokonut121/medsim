import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="shell">
      <section className="hero">
        <div className="eyebrow">MedSentinel</div>
        <div className="hero-grid">
          <div>
            <h1>World models for hospital safety, streamed into action.</h1>
            <p className="muted" style={{ fontSize: "1.1rem", maxWidth: 680 }}>
              Select a facility, auto-acquire public imagery, synthesize a Gaussian-splat world model, and deploy
              six specialized clinical safety agent teams with live findings in under 30 minutes.
            </p>
            <div className="cta-row">
              <Link className="button" href="/dashboard">
                Open dashboard
              </Link>
              <Link className="button secondary" href="/facility/new">
                Onboard facility
              </Link>
            </div>
          </div>
          <div className="stats-grid">
            <div className="stat">
              <div className="eyebrow">Six domains</div>
              <h3>HAI, meds, falls, code blue, flow, handoff</h3>
            </div>
            <div className="stat">
              <div className="eyebrow">Security layer</div>
              <h3>IRIS Secure Wallet, FHIR R4, RBAC, audit log</h3>
            </div>
            <div className="stat">
              <div className="eyebrow">Frontend</div>
              <h3>Next.js 15, Mapbox, React Three Fiber, live WebSockets</h3>
            </div>
            <div className="stat">
              <div className="eyebrow">Output</div>
              <h3>3D annotations, PDF exports, FHIR DiagnosticReports</h3>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

