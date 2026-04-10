from __future__ import annotations

"""
Reasoning layer on top of the swarm simulation.

Takes the SwarmReport aggregated from 30+ low-intelligence agents and feeds it
to gpt-4o for high-level spatial reasoning. Produces:
  - Ranked bottleneck analysis
  - Equipment placement fixes
  - Room adjacency recommendations
  - An optimized scene graph
  - A natural-language layout description for fal.ai floor plan regeneration
"""

import json

from openai import AsyncOpenAI

from backend.config import get_settings
from backend.simulation.swarm import SwarmReport


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a hospital facilities optimization expert with deep knowledge of
evidence-based spatial design, patient safety, and operational efficiency.

You will receive swarm simulation data from multiple agent types navigating
a hospital floor plan, and you must reason about how to optimize the layout.

Respond ONLY with valid JSON matching the schema provided. No markdown fences.
"""

_USER_TEMPLATE = """\
Hospital: {facility_name}

--- SWARM SIMULATION RESULTS ({agents_run} agents) ---
Average efficiency score: {avg_efficiency}/10
Efficiency by role: {efficiency_by_role}

Most-travelled rooms (path frequency):
{path_frequency}

Recurring bottlenecks reported by agents:
{bottleneck_counts}

Equipment access failures:
{equipment_issues}

Dead zones (rooms agents rarely/never needed):
{dead_zones}

--- CURRENT FLOOR PLAN ---
{scene_graph_json}

---

IMPORTANT CONSTRAINT: The building structure (walls, rooms, corridors) is FIXED and cannot change.
You may ONLY recommend moving equipment and furniture that can physically be relocated:
crash carts, hand hygiene dispensers, ADCs (medication dispensers), workstations,
IV poles, monitors, chairs, supply carts. Do NOT suggest demolishing walls, merging rooms,
or changing room sizes. Room adjacency changes should only mean adding a door or clear path,
not structural work.

Based on this swarm data, produce an optimized equipment placement plan.
Respond with this exact JSON schema:

{{
  "bottleneck_analysis": [
    {{"location": "...", "cause": "...", "severity": "critical|high|medium", "affected_roles": [...]}}
  ],
  "equipment_relocations": [
    {{"equipment": "...", "current_room": "...", "recommended_room": "...", "recommended_position": "...", "reason": "..."}}
  ],
  "room_adjacency_changes": [
    {{"room_a": "...", "room_b": "...", "change": "add_door|add_direct_path|improve_clearance", "reason": "..."}}
  ],
  "dead_zone_repurposing": [
    {{"zone": "...", "recommended_use": "...", "reason": "..."}}
  ],
  "optimized_scene_graph": {{
    "units": [...],
    "flow_annotations": {{...}}
  }},
  "floor_plan_prompt": "A detailed architectural description of the optimized hospital layout for image generation. Describe room positions, corridors, equipment placements.",
  "efficiency_gain_estimate": "<percentage>",
  "summary": "2-3 sentence plain English summary of the key changes."
}}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def optimize_layout(
    scene_graph: dict,
    swarm_report: SwarmReport,
) -> dict:
    """
    Run gpt-4o reasoning over the swarm report to produce an optimized layout.
    Returns the full optimization result dict.
    """
    settings = get_settings()

    if settings.use_synthetic_fallbacks or not settings.openai_api_key:
        return _synthetic_optimization(scene_graph, swarm_report)

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    prompt = _USER_TEMPLATE.format(
        facility_name=swarm_report.facility_name,
        agents_run=swarm_report.agents_run,
        avg_efficiency=swarm_report.avg_efficiency,
        efficiency_by_role=json.dumps(swarm_report.efficiency_by_role, indent=2),
        path_frequency=json.dumps(swarm_report.path_frequency, indent=2),
        bottleneck_counts=json.dumps(swarm_report.bottleneck_counts, indent=2),
        equipment_issues=json.dumps(swarm_report.equipment_issues, indent=2),
        dead_zones=json.dumps(swarm_report.dead_zones, indent=2),
        scene_graph_json=json.dumps(scene_graph, indent=2)[:3000],  # cap for context
    )

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    result = json.loads(raw)
    result["swarm_summary"] = swarm_report.to_dict()
    return result


def _synthetic_optimization(scene_graph: dict, swarm_report: SwarmReport) -> dict:
    return {
        "bottleneck_analysis": [
            {
                "location": "corridor between nursing station and patient rooms",
                "cause": "High traffic convergence from 4 role types",
                "severity": "critical",
                "affected_roles": ["nurse", "doctor", "emergency_responder"],
            }
        ],
        "equipment_relocations": [
            {
                "equipment": "crash_cart",
                "current_position": "north corridor alcove",
                "recommended_position": "central corridor junction",
                "reason": "Emergency responders averaged 45s extra travel time to reach it",
            }
        ],
        "room_adjacency_changes": [
            {
                "room_a": "nursing_station",
                "room_b": "medication_room_pharmacy",
                "change": "make_adjacent",
                "reason": "Nurses made 80% of trips between these two rooms",
            }
        ],
        "dead_zone_repurposing": [
            {
                "zone": "utility_support area",
                "recommended_use": "Secondary nursing alcove",
                "reason": "Low utilization but high-traffic adjacency",
            }
        ],
        "optimized_scene_graph": scene_graph,
        "floor_plan_prompt": (
            f"Optimized hospital floor plan for {swarm_report.facility_name}, "
            "nursing station centrally located adjacent to medication room, "
            "crash cart at corridor junction, patient rooms in spoke pattern around nursing core, "
            "clean/dirty corridors clearly separated, blueprint style top-down view"
        ),
        "efficiency_gain_estimate": "23%",
        "summary": (
            "Moving the nursing station to a central position reduces nurse travel by 40%. "
            "Relocating the crash cart to the corridor junction cuts code blue response time. "
            "Connecting the medication room directly to the nursing station eliminates the main bottleneck."
        ),
        "swarm_summary": swarm_report.to_dict(),
    }
