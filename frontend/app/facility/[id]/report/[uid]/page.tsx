import { buildApiUrl } from "@/lib/runtime";

export default async function ReportPage({
  params
}: {
  params: Promise<{ id: string; uid: string }>;
}) {
  const { id, uid } = await params;

  return (
    <main className="shell">
      <div className="panel">
        <div className="eyebrow">Facility {id}</div>
        <h1 className="page-title">Report export</h1>
        <p className="muted">
          Generate PDF and manifest outputs, or request the FHIR DiagnosticReport representation for unit {uid}.
        </p>
        <div className="cta-row">
          <a className="button" href={buildApiUrl(`/api/reports/${uid}/pdf`)}>
            Download PDF
          </a>
          <a className="button secondary" href={buildApiUrl(`/api/reports/${uid}/manifest`)}>
            Download manifest
          </a>
        </div>
      </div>
    </main>
  );
}
