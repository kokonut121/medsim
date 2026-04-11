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

  return (
    <div style={{ background: "var(--paper)", minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "24px" }}>

      <Link href="/" style={{ textDecoration: "none", marginBottom: 40 }}>
        <div style={{ fontFamily: "var(--font-display-stack)", fontSize: 22, fontWeight: 700, color: "var(--ink)", letterSpacing: "-0.03em" }}>
          Med<span style={{ color: "var(--signal)" }}>Sentinel</span>
        </div>
      </Link>

      <div style={{
        width: "100%", maxWidth: 400,
        background: "var(--paper-hi)",
        border: "1px solid var(--chalk-hard)",
        borderRadius: 2,
        padding: "36px 32px",
        boxShadow: "5px 5px 0 var(--ink)",
      }}>
        <div style={{ fontFamily: "var(--font-mono-stack)", fontSize: 10, letterSpacing: "0.22em", textTransform: "uppercase", color: "var(--mercury)", marginBottom: 16 }}>
          Sign in
        </div>
        <h1 style={{ margin: "0 0 6px", fontFamily: "var(--font-display-stack)", fontSize: 28, fontWeight: 300, color: "var(--ink)", letterSpacing: "-0.03em" }}>
          Welcome back.
        </h1>
        <p style={{ margin: "0 0 28px", color: "var(--mercury)", fontSize: 13, fontFamily: "var(--font-body-stack)" }}>
          Access your facility intelligence dashboard.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 10, fontFamily: "var(--font-mono-stack)", color: "var(--mercury)", letterSpacing: "0.16em", textTransform: "uppercase" }}>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@hospital.org" required style={inputStyle} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontSize: 10, fontFamily: "var(--font-mono-stack)", color: "var(--mercury)", letterSpacing: "0.16em", textTransform: "uppercase" }}>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required style={inputStyle} />
          </div>

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
            {loading ? "Signing in…" : "Sign in →"}
          </button>
        </form>

        <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "20px 0" }}>
          <div style={{ flex: 1, height: 1, background: "var(--chalk-hard)" }} />
          <span style={{ fontSize: 11, color: "var(--mercury)", fontFamily: "var(--font-mono-stack)", letterSpacing: "0.1em" }}>or</span>
          <div style={{ flex: 1, height: 1, background: "var(--chalk-hard)" }} />
        </div>

        <button onClick={handleDemo} disabled={loading} style={{
          width: "100%", padding: "11px",
          background: "transparent", color: "var(--mercury)",
          border: "1px solid var(--chalk-hard)", borderRadius: 2,
          fontSize: 11, fontFamily: "var(--font-mono-stack)",
          letterSpacing: "0.1em", textTransform: "uppercase",
          cursor: loading ? "not-allowed" : "pointer",
        }}>
          Demo account →
        </button>

        <p style={{ marginTop: 24, textAlign: "center", fontSize: 13, color: "var(--mercury)", fontFamily: "var(--font-body-stack)" }}>
          No account?{" "}
          <Link href="/signup" style={{ color: "var(--ink)", textDecoration: "underline" }}>
            Request access
          </Link>
        </p>
      </div>
    </div>
  );
}
