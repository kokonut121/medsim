"""
Domain Swarm Teams
==================
3 parallel sub-agents per domain, each analyzing the canonical spatial bundle.
LLMs emit room_id / equipment_ref references only — no raw coordinates.
Grounding (backend.agents.grounding) snaps those to bundle anchors.

Sub-agent catalog:
  ICA: entry-hygiene, isolation/asepsis, clean-dirty flow
  MSA: ADC placement, prep-zone distraction, med-handoff infrastructure
  FRA: bedside clearance, sightline, call-light/access
  ERA: crash-cart coverage, emergency path, call-system
  PFA: corridor bottleneck, transfer distance, discharge/turnover
  SCA: handoff-zone, monitoring hub, quiet consultation
"""
from __future__ import annotations

import asyncio

from backend.agents.providers.base import LLMProvider

# ---------------------------------------------------------------------------
# Bundle → compact prompt text (no room_index — keeps LLM context lean)
# ---------------------------------------------------------------------------

def _bundle_text(bundle: dict) -> str:
    lines = ["=== SPATIAL BUNDLE ==="]
    for room in bundle.get("rooms", []):
        eq_parts = []
        for e in room.get("equipment", []):
            state = "blocked" if not e.get("accessible", True) else "ok"
            eq_parts.append(f"{e['type']}({state},conf={e.get('confidence',0):.2f})")
        eq_str = "; ".join(eq_parts) or "none"
        sight = "nursing_visible=YES" if room.get("sightline_to_nursing_station") else "nursing_visible=NO"
        tags = room.get("zone_tags", [])
        lines.append(
            f"  {room['room_id']} type={room['type']} zones={tags} {sight} "
            f"adj={room.get('adjacency',[])} equip=[{eq_str}]"
        )

    zi = bundle.get("zone_index", {})
    clean = [r for r, t in zi.items() if "clean_corridor" in t]
    dirty = [r for r, t in zi.items() if "dirty_corridor" in t]
    if clean:
        lines.append(f"Clean corridors: {clean}")
    if dirty:
        lines.append(f"Dirty corridors: {dirty}")

    vis = bundle.get("visibility_pairs", [])
    if vis:
        lines.append(f"Nursing-visible rooms: {[v['observer'] for v in vis]}")

    lines.append("=== END BUNDLE ===")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema injected into every system prompt
# ---------------------------------------------------------------------------

_SCHEMA = """
Respond ONLY with valid JSON: {"findings": [...]}
Each finding must match this schema exactly (0–5 findings max):
{
  "room_id": "<exact room_id from the bundle above>",
  "equipment_ref": "<equipment type string from the bundle, or omit for room-level>",
  "severity": "CRITICAL" | "HIGH" | "ADVISORY",
  "confidence": <0.0–1.0>,
  "label_text": "<≤80 chars>",
  "recommendation": "<≤150 chars, actionable>",
  "evidence": "<1 sentence citing bundle data>"
}
RULES:
- Only reference room_ids and equipment types that appear in the bundle.
- Do NOT invent rooms or equipment.
- Return {"findings": []} if no issues found.
"""


# ---------------------------------------------------------------------------
# Domain agent definitions
# ---------------------------------------------------------------------------

_DOMAINS: dict[str, list[dict]] = {
    "ICA": [
        {
            "sub_agent": "Entry-Hygiene-Auditor",
            "system": (
                "You are an infection control specialist auditing hand hygiene compliance.\n"
                "For each patient-care room and entry point: verify hand_hygiene_dispenser is present "
                "AND accessible (accessible=ok). Flag missing dispensers as CRITICAL, blocked as HIGH, "
                "low confidence (<0.75) as HIGH.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Isolation-Asepsis-Auditor",
            "system": (
                "You are an infection control specialist auditing isolation and asepsis infrastructure.\n"
                "Check patient-care rooms for hand hygiene at entry AND clean linen/supply separation. "
                "Flag rooms with no hand_hygiene_dispenser of any kind as CRITICAL. "
                "Flag simulation/ICU rooms sharing supply paths with dirty corridors as HIGH.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Clean-Dirty-Flow-Auditor",
            "system": (
                "You are an infection control specialist auditing clean/dirty traffic flow separation.\n"
                "Look at clean_corridors and dirty_corridors. Identify rooms that are patient-care but "
                "adjacent to dirty-corridor rooms without a clean-corridor buffer. "
                "Flag direct clean+dirty merges as HIGH, risk adjacency as ADVISORY.\n" + _SCHEMA
            ),
        },
    ],
    "MSA": [
        {
            "sub_agent": "ADC-Placement-Auditor",
            "system": (
                "You are a medication safety specialist auditing automated dispensing cabinet (ADC) coverage.\n"
                "For each medication_room_pharmacy room: verify adc is present and accessible. "
                "Missing ADC = HIGH. Blocked ADC = HIGH.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "PrepZone-Distraction-Auditor",
            "system": (
                "You are a medication safety specialist auditing medication preparation zone safety.\n"
                "Medication rooms should have a workstation (for barcode verification) and low through-traffic. "
                "Missing workstation = ADVISORY. Medication room adjacent to high-traffic corridor = ADVISORY.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Med-Handoff-Infrastructure-Auditor",
            "system": (
                "You are a medication safety specialist auditing medication handoff paths.\n"
                "Check nav_edges: if a patient room is more than 2 hops from any medication room, flag as ADVISORY. "
                "If a supply/utility room is the only medication-adjacent room, flag as HIGH.\n" + _SCHEMA
            ),
        },
    ],
    "FRA": [
        {
            "sub_agent": "Bedside-Clearance-Auditor",
            "system": (
                "You are a fall prevention specialist auditing bedside clearance.\n"
                "For every patient_room and icu_bay: check iv_pole accessibility. "
                "Blocked iv_pole (accessible=blocked) = HIGH fall risk during ambulation.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Sightline-Auditor",
            "system": (
                "You are a fall prevention specialist auditing nursing station sightlines.\n"
                "Every patient_room and icu_bay must have nursing_visible=YES. "
                "nursing_visible=NO = HIGH severity — nurses cannot observe patient falls.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "CallLight-Access-Auditor",
            "system": (
                "You are a fall prevention specialist auditing call light presence.\n"
                "Every patient_room and icu_bay must have call_light present and accessible. "
                "Missing call_light AND nursing_visible=NO = CRITICAL (communication blackout). "
                "Missing call_light but nursing_visible=YES = HIGH.\n" + _SCHEMA
            ),
        },
    ],
    "ERA": [
        {
            "sub_agent": "CrashCart-Coverage-Auditor",
            "system": (
                "You are an emergency response specialist auditing crash cart coverage.\n"
                "Check if any crash_cart exists anywhere in the facility. "
                "If no crash_cart at all: flag every patient room as CRITICAL. "
                "If crash_cart exists but blocked: flag it as CRITICAL.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Emergency-Path-Auditor",
            "system": (
                "You are an emergency response specialist auditing emergency response paths.\n"
                "Check nav_edges: is there a clear corridor path from each patient room to a crash_cart? "
                "Single-corridor dependency (one corridor serves all patient rooms) = HIGH. "
                "Patient room with no direct corridor adjacency = CRITICAL.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "CallSystem-Auditor",
            "system": (
                "You are an emergency response specialist auditing call system coverage.\n"
                "Every patient_room and icu_bay must have call_light. "
                "Missing call_light = HIGH. Missing call_light AND nursing_visible=NO = CRITICAL.\n" + _SCHEMA
            ),
        },
    ],
    "PFA": [
        {
            "sub_agent": "Corridor-Bottleneck-Auditor",
            "system": (
                "You are a patient flow specialist auditing corridor bottlenecks.\n"
                "If a single corridor connects 3+ patient rooms with no alternative route, flag as HIGH. "
                "If only one entry/exit corridor exists for the whole unit, flag as HIGH.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Transfer-Distance-Auditor",
            "system": (
                "You are a patient flow specialist auditing patient transfer distances.\n"
                "Use nav_edges distances. If a patient room's nearest crash_cart is more than 3 hops or "
                "total path > 20m, flag as ADVISORY. If no crash_cart reachable, flag as HIGH.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Discharge-Turnover-Auditor",
            "system": (
                "You are a patient flow specialist auditing discharge and supply turnover.\n"
                "Check that supply/utility rooms can reach patient rooms without crossing clean_corridors "
                "through dirty paths. Supply room adjacent only to patient care with no corridor buffer = ADVISORY.\n"
                + _SCHEMA
            ),
        },
    ],
    "SCA": [
        {
            "sub_agent": "Handoff-Zone-Auditor",
            "system": (
                "You are a safe communication specialist auditing nursing station handoff zones.\n"
                "Nursing_hub rooms must have a workstation (EHR access). Missing = HIGH. "
                "Patient rooms with nursing_visible=NO AND no call_light = CRITICAL communication blackout.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Monitoring-Hub-Auditor",
            "system": (
                "You are a safe communication specialist auditing central monitoring.\n"
                "Check visibility_pairs: nursing hub rooms should observe all patient_care rooms. "
                "Any patient_care room not in visibility_pairs = HIGH (blind spot). "
                "If no nursing_hub rooms exist: flag each patient room as CRITICAL.\n" + _SCHEMA
            ),
        },
        {
            "sub_agent": "Quiet-Consultation-Auditor",
            "system": (
                "You are a safe communication specialist auditing private consultation space.\n"
                "Look for rooms with zone_tags containing 'consultation'. "
                "If no consultation room exists for the unit: flag as ADVISORY. "
                "If consultation rooms are adjacent to high-traffic corridors: flag as ADVISORY.\n" + _SCHEMA
            ),
        },
    ],
}


# ---------------------------------------------------------------------------
# Sub-agent runner
# ---------------------------------------------------------------------------

async def _run_sub_agent(
    provider: LLMProvider,
    domain: str,
    agent_def: dict,
    bundle_text: str,
) -> list[dict]:
    user = (
        f"Analyze this facility spatial bundle for domain {domain} "
        f"sub-agent role '{agent_def['sub_agent']}':\n\n{bundle_text}"
    )
    try:
        result = await provider.complete_json(
            agent_def["system"],
            user,
            temperature=0.3,
            max_tokens=900,
        )
        candidates: list = result.get("findings", []) if isinstance(result, dict) else result
    except Exception:
        return []

    for c in candidates:
        c["domain"] = domain
        c["sub_agent"] = agent_def["sub_agent"]

    return candidates


# ---------------------------------------------------------------------------
# Domain swarm entry point
# ---------------------------------------------------------------------------

async def run_domain_swarm(
    provider: LLMProvider,
    domain: str,
    bundle: dict,
) -> list[dict]:
    """Run all 3 sub-agents for a domain in parallel. Returns raw candidates."""
    agent_defs = _DOMAINS.get(domain, [])
    if not agent_defs:
        return []

    text = _bundle_text(bundle)
    tasks = [_run_sub_agent(provider, domain, a, text) for a in agent_defs]
    results = await asyncio.gather(*tasks)
    return [c for sub in results for c in sub]


DOMAIN_AGENTS = _DOMAINS
