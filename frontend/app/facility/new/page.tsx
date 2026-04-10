import { FacilityOnboardingForm } from "@/components/facility/FacilityOnboardingForm";

export default function FacilityNewPage() {
  return (
    <main className="shell">
      <div className="panel">
        <div className="eyebrow">Facility onboarding</div>
        <h1 className="page-title">Search, geocode, auto-acquire</h1>
        <FacilityOnboardingForm />
      </div>
    </main>
  );
}
