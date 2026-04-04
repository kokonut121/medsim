export default function FacilityNewPage() {
  return (
    <main className="shell">
      <div className="panel">
        <div className="eyebrow">Facility onboarding</div>
        <h1 className="page-title">Search, geocode, auto-acquire</h1>
        <form className="inline-form" style={{ marginTop: 20 }}>
          <input
            aria-label="Facility name"
            defaultValue="MedSentinel Academic Medical Center"
            style={{ padding: 14, borderRadius: 18, border: "1px solid var(--border)", minWidth: 280 }}
          />
          <input
            aria-label="Address"
            defaultValue="123 Health Ave, Chicago, IL"
            style={{ padding: 14, borderRadius: 18, border: "1px solid var(--border)", minWidth: 360 }}
          />
          <button className="button" type="submit">
            Create facility
          </button>
        </form>
      </div>
    </main>
  );
}

