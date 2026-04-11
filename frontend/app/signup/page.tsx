"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function SignupPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => { setLoading(false); setSubmitted(true); }, 900);
  }

  const inputStyle: React.CSSProperties = {
    background: "var(--paper-hi)",
    border: "1px solid var(--chalk-hard)",
    borderRadius: 2,
    padding: "10px 14px",
    color: "var(--ink)",
    fontSize: 14,
    fontFamily: "var(--font-body-stack)",
    outline: "none",
    width: "100%",
    boxSizing: "border-box",
  };

  if (submitted) {
    return (
      <div style={{ background: "var(--paper)", minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "24px", textAlign: "center" }}>
        <div style={{ fontFamily: "var(--font-mono-stack)", fontSize: 28, color: "var(--signal)", marginBottom: 16 }}>✓</div>
        <h2 style={{ fontFamily: "var(--font-display-stack)", color: "var(--ink)", margin: "0 0 12px", fontSize: 28, fontWeight: 300 }}>Request received.</h2>
        <p style={{ color: "var(--mercury)", maxWidth: 360, margin: "0 0 28px", fontFamily: "var(--font-body-stack)", lineHeight: 1.6 }}>
          We'll review your facility details and reach out within 24 hours to set up your account.
        </p>
        <Link href="/login" style={{
          padding: "12px 28px", background: "var(--ink)", color: "var(--paper-hi)",
          borderRadius: 2, textDecoration: "none", fontSize: 11, fontWeight: 600,
          fontFamily: "var(--font-mono-stack)", letterSpacing: "0.12em", textTransform: "uppercase",
        }}>
          Back to sign in →
        </Link>
      </div>
    );
  }

  return (
    <div style={{ background: "var(--paper)", minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "24px" }}>

      <Link href="/" style={{ textDecoration: "none", marginBottom: 40 }}>
        <div style={{ fontFamily: "var(--font-display-stack)", fontSize: 22, fontWeight: 700, color: "var(--ink)", letterSpacing: "-0.03em" }}>
          Med<span style={{ color: "var(--signal)" }}>Sim</span>
        </div>
      </Link>

      <div style={{
        width: "100%", maxWidth: 440,
        background: "var(--paper-hi)",
        border: "1px solid var(--chalk-hard)",
        borderRadius: 2,
        padding: "36px 32px",
        boxShadow: "5px 5px 0 var(--ink)",
      }}>
        <div style={{ fontFamily: "var(--font-mono-stack)", fontSize: 10, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--mercury)", marginBottom: 16 }}>
          Request access
        </div>
        <h1 style={{ margin: "0 0 6px", fontFamily: "var(--font-display-stack)", fontSize: 28, fontWeight: 300, color: "var(--ink)", letterSpacing: "-0.03em" }}>
          Join MedSim.
        </h1>
        <p style={{ margin: "0 0 28px", color: "var(--mercury)", fontSize: 13, fontFamily: "var(--font-body-stack)" }}>
          Currently invite-only. Tell us about your facility.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {[
            { label: "Full name",     type: "text",  placeholder: "Dr. Jane Smith" },
            { label: "Work email",    type: "email", placeholder: "you@hospital.org" },
            { label: "Facility name", type: "text",  placeholder: "County Trauma Center" },
            { label: "Role / title",  type: "text",  placeholder: "Chief Medical Officer" },
          ].map(({ label, type, placeholder }) => (
            <div key={label} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 10, fontFamily: "var(--font-mono-stack)", color: "var(--mercury)", letterSpacing: "0.16em", textTransform: "uppercase" }}>{label}</label>
              <input type={type} placeholder={placeholder} required style={inputStyle} />
            </div>
          ))}

          <button type="submit" disabled={loading} style={{
            marginTop: 8, padding: "12px",
            background: "var(--ink)", color: "var(--paper-hi)",
            border: "none", borderRadius: 2,
            fontSize: 11, fontWeight: 600,
            fontFamily: "var(--font-mono-stack)",
            letterSpacing: "0.12em", textTransform: "uppercase",
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.6 : 1,
          }}>
            {loading ? "Submitting…" : "Submit request →"}
          </button>
        </form>

        <p style={{ marginTop: 20, textAlign: "center", fontSize: 13, color: "var(--mercury)", fontFamily: "var(--font-body-stack)" }}>
          Already have an account?{" "}
          <Link href="/login" style={{ color: "var(--ink)", textDecoration: "underline" }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
