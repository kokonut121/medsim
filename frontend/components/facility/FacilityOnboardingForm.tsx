"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

export function FacilityOnboardingForm() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [name, setName] = useState("Massachusetts General Hospital");
  const [address, setAddress] = useState("55 Fruit St, Boston, MA 02114");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    startTransition(async () => {
      try {
        const facility = await api.createFacility({
          name,
          address,
          unit_name: "Trauma Center",
          unit_type: "Trauma",
          floor: 1
        });
        router.push(`/facility/${facility.facility_id}`);
      } catch (submitError) {
        setError(submitError instanceof Error ? submitError.message : "Unable to create facility");
      }
    });
  }

  return (
    <form className="inline-form" style={{ marginTop: 20, display: "grid" }} onSubmit={onSubmit}>
      <input
        aria-label="Facility name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        style={{ padding: 14, borderRadius: 18, border: "1px solid var(--border)", minWidth: 280 }}
      />
      <input
        aria-label="Address"
        value={address}
        onChange={(event) => setAddress(event.target.value)}
        style={{ padding: 14, borderRadius: 18, border: "1px solid var(--border)", minWidth: 360 }}
      />
      <button className="button" type="submit" disabled={isPending}>
        {isPending ? "Creating facility..." : "Create facility"}
      </button>
      {error ? (
        <p className="muted" style={{ marginBottom: 0, color: "var(--critical)" }}>
          {error}
        </p>
      ) : null}
    </form>
  );
}
