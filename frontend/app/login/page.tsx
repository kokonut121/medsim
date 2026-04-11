"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => router.push("/dashboard"), 800);
  }

  function handleDemo() {
    setEmail("demo@medsentinel.ai");
    setPassword("sentinel2025");
    setLoading(true);
    setTimeout(() => router.push("/dashboard"), 600);
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
      {/* logo */}
      <Link href="/" style={{ textDecoration: "none", marginBottom: 40 }}>
        <div style={{
          fontFamily: "var(--font-display-stack)",
          fontSize: 22,
          fontWeight: 700,
          color: "var(--bone)",
          letterSpacing: "-0.03em",
        }}>
          Med<span style={{ color: "var(--phosphor)" }}>Sentinel</span>
        </div>
      </Link>

      <div style={{
        width: "100%",
        maxWidth: 400,
        background: "var(--midnight-card)",
        border: "1px solid var(--bone-chalk)",
        borderRadius: 10,
        padding: "36px 32px",
      }}>
        <h1 style={{
          margin: "0 0 6px",
          fontFamily: "var(--font-display-stack)",
          fontSize: 24,
          fontWeight: 700,
          color: "var(--bone)",
          letterSpacing: "-0.03em",
        }}>
          Sign in
        </h1>
        <p style={{ margin: "0 0 28px", color: "var(--bone-soft)", fontSize: 14 }}>
          Access your facility intelligence dashboard.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 12, fontFamily: "var(--font-mono-stack)", color: "var(--bone-soft)", letterSpacing: "0.08em" }}>
              EMAIL
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@hospital.org"
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
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 12, fontFamily: "var(--font-mono-stack)", color: "var(--bone-soft)", letterSpacing: "0.08em" }}>
              PASSWORD
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
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
              fontFamily: "var(--font-body-stack)",
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "20px 0" }}>
          <div style={{ flex: 1, height: 1, background: "var(--bone-chalk)" }} />
          <span style={{ fontSize: 12, color: "var(--bone-soft)", fontFamily: "var(--font-mono-stack)" }}>or</span>
          <div style={{ flex: 1, height: 1, background: "var(--bone-chalk)" }} />
        </div>

        <button
          onClick={handleDemo}
          disabled={loading}
          style={{
            width: "100%",
            padding: "11px",
            background: "transparent",
            color: "var(--bone-soft)",
            border: "1px solid var(--bone-chalk)",
            borderRadius: 6,
            fontSize: 14,
            fontFamily: "var(--font-body-stack)",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          Continue with demo account
        </button>

        <p style={{ marginTop: 24, textAlign: "center", fontSize: 13, color: "var(--bone-soft)" }}>
          No account?{" "}
          <Link href="/signup" style={{ color: "var(--phosphor)", textDecoration: "none" }}>
            Request access
          </Link>
        </p>
      </div>
    </main>
  );
}
