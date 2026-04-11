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
    setTimeout(() => {
      setLoading(false);
      setSubmitted(true);
    }, 900);
  }

  if (submitted) {
    return (
      <main style={{
        minHeight: "100vh",
        background: "var(--midnight)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        textAlign: "center",
      }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>✓</div>
        <h2 style={{ fontFamily: "var(--font-display-stack)", color: "var(--bone)", margin: "0 0 12px", fontSize: 24 }}>Request received</h2>
        <p style={{ color: "var(--bone-soft)", maxWidth: 360, margin: "0 0 28px" }}>
          We'll review your facility details and reach out within 24 hours to set up your account.
        </p>
        <Link href="/login" style={{
          padding: "10px 24px",
          background: "var(--phosphor)",
          color: "#fff",
          borderRadius: 6,
          textDecoration: "none",
          fontSize: 14,
          fontWeight: 600,
        }}>
          Back to sign in
        </Link>
      </main>
    );
  }

  return (
    <main style={{
      minHeight: "100vh",
      background: "var(--midnight)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "24px",
    }}>
      <Link href="/" style={{ textDecoration: "none", marginBottom: 40 }}>
        <div style={{ fontFamily: "var(--font-display-stack)", fontSize: 22, fontWeight: 700, color: "var(--bone)", letterSpacing: "-0.03em" }}>
          Med<span style={{ color: "var(--phosphor)" }}>Sentinel</span>
        </div>
      </Link>

      <div style={{
        width: "100%",
        maxWidth: 440,
        background: "var(--midnight-card)",
        border: "1px solid var(--bone-chalk)",
        borderRadius: 10,
        padding: "36px 32px",
      }}>
        <h1 style={{ margin: "0 0 6px", fontFamily: "var(--font-display-stack)", fontSize: 24, fontWeight: 700, color: "var(--bone)", letterSpacing: "-0.03em" }}>
          Request access
        </h1>
        <p style={{ margin: "0 0 28px", color: "var(--bone-soft)", fontSize: 14 }}>
          MedSentinel is currently invite-only. Tell us about your facility.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {[
            { label: "FULL NAME",      type: "text",  placeholder: "Dr. Jane Smith" },
            { label: "WORK EMAIL",     type: "email", placeholder: "you@hospital.org" },
            { label: "FACILITY NAME",  type: "text",  placeholder: "County Trauma Center" },
            { label: "ROLE / TITLE",   type: "text",  placeholder: "Chief Medical Officer" },
          ].map(({ label, type, placeholder }) => (
            <div key={label} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: 12, fontFamily: "var(--font-mono-stack)", color: "var(--bone-soft)", letterSpacing: "0.08em" }}>{label}</label>
              <input
                type={type}
                placeholder={placeholder}
                required
                style={{
                  background: "var(--midnight-elev)",
                  border: "1px solid var(--bone-chalk)",
                  borderRadius: 6,
                  padding: "10px 14px",
                  color: "var(--bone)",
                  fontSize: 14,
                  fontFamily: "var(--font-body-stack)",
                  outline: "none",
                }}
              />
            </div>
          ))}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 8,
              padding: "12px",
              background: "var(--phosphor)",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              fontSize: 14,
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "Submitting…" : "Submit request"}
          </button>
        </form>

        <p style={{ marginTop: 20, textAlign: "center", fontSize: 13, color: "var(--bone-soft)" }}>
          Already have an account?{" "}
          <Link href="/login" style={{ color: "var(--phosphor)", textDecoration: "none" }}>Sign in</Link>
        </p>
      </div>
    </main>
  );
}
