"use client";

import { useState } from "react";

type Props = {
  disabled?: boolean;
  defaultAgentsPerRole?: number;
  onSubmit: (prompt: string, agentsPerRole: number) => void;
};

const EXAMPLE_PROMPTS = [
  "heavily congested flow of burn victims from a factory fire",
  "multi-vehicle crash with blunt trauma and airway compromise",
  "mass stabbing victims from a street altercation"
];

export function ScenarioPromptForm({ disabled, defaultAgentsPerRole = 3, onSubmit }: Props) {
  const [prompt, setPrompt] = useState("");
  const [agentsPerRole, setAgentsPerRole] = useState(defaultAgentsPerRole);

  const tooShort = prompt.trim().length < 5;

  return (
    <form
      className="panel"
      onSubmit={(event) => {
        event.preventDefault();
        if (tooShort || disabled) return;
        onSubmit(prompt.trim(), agentsPerRole);
      }}
      style={{ display: "grid", gap: 14 }}
    >
      <div>
        <div className="eyebrow">Scenario prompt</div>
        <h2 style={{ margin: "8px 0 10px" }}>Simulate a crisis</h2>
        <p className="muted" style={{ margin: 0 }}>
          Describe the incoming surge in plain English. A swarm of role-playing agents will walk
          the floor plan as doctors, nurses, patients, and commanders, and a supervising reasoner
          will produce a tactical best-plan report.
        </p>
      </div>

      <label>
        <div className="muted" style={{ marginBottom: 6 }}>Scenario</div>
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder={EXAMPLE_PROMPTS[0]}
          rows={3}
          maxLength={500}
          disabled={disabled}
          style={{ width: "100%", padding: 10, fontSize: 14, resize: "vertical" }}
        />
      </label>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {EXAMPLE_PROMPTS.map((example) => (
          <button
            key={example}
            type="button"
            className="button secondary"
            disabled={disabled}
            onClick={() => setPrompt(example)}
            style={{ fontSize: 12 }}
          >
            {example.slice(0, 46)}…
          </button>
        ))}
      </div>

      <label className="muted">
        Agents per role: {agentsPerRole}
        <input
          type="range"
          min={1}
          max={8}
          step={1}
          value={agentsPerRole}
          disabled={disabled}
          onChange={(event) => setAgentsPerRole(Number(event.target.value))}
          style={{ display: "block", width: "100%" }}
        />
      </label>

      <div className="cta-row">
        <button type="submit" className="button" disabled={disabled || tooShort}>
          {disabled ? "Running…" : "Launch swarm"}
        </button>
        <span className="muted" style={{ fontSize: 12 }}>
          {prompt.trim().length}/500 chars
        </span>
      </div>
    </form>
  );
}
