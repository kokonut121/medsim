import { BackLink } from "@/components/ui/BackLink";
import { FacilityOnboardingForm } from "@/components/facility/FacilityOnboardingForm";

export default function FacilityNewPage() {
  return (
    <main className="shell">
      <BackLink href="/dashboard" label="Dashboard" />
      <div className="panel">
        <div className="eyebrow">Facility onboarding</div>
        <h1 className="page-title">Search, geocode, auto-acquire</h1>
        <FacilityOnboardingForm />
      </div>
    </main>
  );
}
