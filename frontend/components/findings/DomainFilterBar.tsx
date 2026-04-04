"use client";

import { DOMAIN_COLORS } from "@/lib/constants";
import { useStore } from "@/store";
import type { Domain } from "@/types";

const domains: Domain[] = ["ICA", "MSA", "FRA", "ERA", "PFA", "SCA"];

export function DomainFilterBar() {
  const activeDomains = useStore((state) => state.activeDomains);
  const toggleDomain = useStore((state) => state.toggleDomain);

  return (
    <div className="filter-row">
      {domains.map((domain) => {
        const active = activeDomains.includes(domain);
        return (
          <button
            key={domain}
            className="pill"
            onClick={() => toggleDomain(domain)}
            style={{
              background: active ? DOMAIN_COLORS[domain] : "transparent",
              color: active ? "white" : DOMAIN_COLORS[domain],
              border: `1px solid ${DOMAIN_COLORS[domain]}`
            }}
          >
            {domain}
          </button>
        );
      })}
    </div>
  );
}

