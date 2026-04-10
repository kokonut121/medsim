from __future__ import annotations

"""
Swarm simulation layer.

Runs N low-intelligence agents per role type in parallel using gpt-4o-mini.
Each agent receives a compact scene graph and simulates a single navigation
journey through the hospital space, reporting paths, bottlenecks, and
equipment friction points.

Results are aggregated into a SwarmReport used by the optimizer.
"""

import asyncio
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from backend.config import get_settings


# ---------------------------------------------------------------------------
# Agent role definitions
# ---------------------------------------------------------------------------

@dataclass
class AgentRole:
    role: str
    description: str
    start_hint: str
    goal_hint: str


AGENT_ROLES: list[AgentRole] = [
    AgentRole(
        role="patient",
        description="A patient arriving at the ED needing to reach an assigned room.",
        start_hint="main entrance / ED triage",
        goal_hint="assigned patient room",
    ),
    AgentRole(
        role="nurse",
        description="A floor nurse making rounds between the nursing station and patient rooms, then retrieving medication.",
        start_hint="nursing station",
        goal_hint="patient room, then medication room, then back to nursing station",
    ),
    AgentRole(
        role="emergency_responder",
        description="An emergency responder racing to a code blue, needing the crash cart.",
        start_hint="nearest corridor",
        goal_hint="crash cart location, then critical patient room",
    ),
    AgentRole(
        role="doctor",
        description="A physician moving between patient consultations and the medication preparation area.",
        start_hint="corridor near nursing station",
        goal_hint="patient room, medication room, second patient room",
    ),
    AgentRole(
        role="visitor",
        description="A visitor navigating from the lobby to find a patient room with no prior knowledge of the layout.",
        start_hint="lobby / main entrance",
        goal_hint="patient room",
    ),
    AgentRole(
        role="supply_staff",
        description="Supply staff restocking patient rooms from the utility room.",
        start_hint="utility / support room",
        goal_hint="each patient room in sequence",
    ),
]


# ---------------------------------------------------------------------------
# Scene graph summary builder (compact for token efficiency)
# ---------------------------------------------------------------------------

def _summarize_scene_graph(scene_graph: dict) -> str:
    lines: list[str] = []
    for unit in scene_graph.get("units", []):
        lines.append(f"Unit: {unit.get('unit_id')} ({unit.get('unit_type', 'unknown')})")
        for room in unit.get("rooms", []):
            equipment = ", ".join(
                e["type"] for e in room.get("equipment", []) if e.get("accessible", True)
            ) or "none"
            adj = ", ".join(room.get("adjacency", []))
            sightline = "✓" if room.get("sightline_to_nursing_station") else "✗"
            lines.append(
                f"  {room['room_id']} [{room.get('type', '?')}] "
                f"area={room.get('area_sqft_estimate', '?')}sqft "
                f"equip=[{equipment}] adj=[{adj}] nursing_sightline={sightline}"
            )
    fa = scene_graph.get("flow_annotations", {})
    lines.append(f"Patient flow: {' -> '.join(str(p) for p in fa.get('patient_flow_paths', [[]])[0] if fa.get('patient_flow_paths'))}")
    lines.append(f"Staff flow:   {' -> '.join(str(p) for p in fa.get('staff_flow_paths', [[]])[0] if fa.get('staff_flow_paths'))}")
    lines.append(f"Clean corridors: {', '.join(fa.get('clean_corridors', []))}")
    lines.append(f"Dirty corridors: {', '.join(fa.get('dirty_corridors', []))}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Single agent run
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a hospital space simulation agent. You will be given a hospital floor plan
and asked to simulate a single person navigating it. Be concise and realistic.
You must respond ONLY with valid JSON — no markdown, no explanation outside the JSON.
"""

_USER_TEMPLATE = """\
Hospital: {facility_name}
Your role: {role} — {description}

Floor plan:
{scene_summary}

Simulate your journey:
- Start: {start_hint}
- Goal: {goal_hint}

Respond with this exact JSON schema:
{{
  "role": "{role}",
  "path": ["room_id_1", "room_id_2", ...],
  "bottlenecks": ["description of any congestion or tight spots"],
  "equipment_issues": ["any equipment that was missing, inaccessible, or too far away"],
  "dead_zones": ["rooms or areas you never needed or couldn't reach"],
  "efficiency_score": <1-10>,
  "notes": "brief observation about layout quality"
}}
"""


async def _run_agent(
    client: AsyncOpenAI,
    role: AgentRole,
    scene_summary: str,
    facility_name: str,
    agent_index: int,
) -> dict:
    prompt = _USER_TEMPLATE.format(
        facility_name=facility_name,
        role=role.role,
        description=role.description,
        scene_summary=scene_summary,
        start_hint=role.start_hint,
        goal_hint=role.goal_hint,
    )
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)
        result["agent_index"] = agent_index
        return result
    except Exception as exc:
        return {
            "role": role.role,
            "path": [],
            "bottlenecks": [],
            "equipment_issues": [],
            "dead_zones": [],
            "efficiency_score": 5,
            "notes": f"Agent error: {exc}",
            "agent_index": agent_index,
        }


# ---------------------------------------------------------------------------
# Swarm report
# ---------------------------------------------------------------------------

@dataclass
class SwarmReport:
    facility_name: str
    agents_run: int
    raw_results: list[dict]

    # Aggregated
    path_frequency: dict[str, int] = field(default_factory=dict)       # room_id -> visit count
    bottleneck_counts: dict[str, int] = field(default_factory=dict)     # phrase -> count
    equipment_issues: dict[str, int] = field(default_factory=dict)      # issue -> count
    dead_zones: list[str] = field(default_factory=list)
    avg_efficiency: float = 0.0
    efficiency_by_role: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "facility_name": self.facility_name,
            "agents_run": self.agents_run,
            "path_frequency": self.path_frequency,
            "bottleneck_counts": self.bottleneck_counts,
            "equipment_issues": self.equipment_issues,
            "dead_zones": self.dead_zones,
            "avg_efficiency": round(self.avg_efficiency, 2),
            "efficiency_by_role": {k: round(v, 2) for k, v in self.efficiency_by_role.items()},
        }


def _aggregate(results: list[dict], facility_name: str) -> SwarmReport:
    path_freq: Counter = Counter()
    bottleneck_raw: list[str] = []
    equipment_raw: list[str] = []
    dead_zone_raw: list[str] = []
    scores: list[float] = []
    scores_by_role: dict[str, list[float]] = defaultdict(list)

    for r in results:
        for room in r.get("path", []):
            path_freq[room] += 1
        bottleneck_raw.extend(r.get("bottlenecks", []))
        equipment_raw.extend(r.get("equipment_issues", []))
        dead_zone_raw.extend(r.get("dead_zones", []))
        score = float(r.get("efficiency_score", 5))
        scores.append(score)
        scores_by_role[r.get("role", "unknown")].append(score)

    # Deduplicate dead zones that appear in most agent runs
    dead_zone_counts = Counter(dead_zone_raw)
    common_dead_zones = [z for z, c in dead_zone_counts.items() if c >= max(2, len(results) // 4)]

    return SwarmReport(
        facility_name=facility_name,
        agents_run=len(results),
        raw_results=results,
        path_frequency=dict(path_freq.most_common(20)),
        bottleneck_counts=dict(Counter(bottleneck_raw).most_common(10)),
        equipment_issues=dict(Counter(equipment_raw).most_common(10)),
        dead_zones=common_dead_zones,
        avg_efficiency=sum(scores) / max(len(scores), 1),
        efficiency_by_role={
            role: sum(s) / max(len(s), 1) for role, s in scores_by_role.items()
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_swarm(
    scene_graph: dict,
    facility_name: str,
    *,
    agents_per_role: int = 5,
) -> SwarmReport:
    """
    Launch `agents_per_role` agents for each of the 6 role types in parallel.
    Default: 5 × 6 = 30 concurrent gpt-4o-mini calls.
    """
    settings = get_settings()

    # Synthetic fallback — no API key
    if settings.use_synthetic_fallbacks or not settings.openai_api_key:
        synthetic = [
            {
                "role": role.role,
                "path": ["ENTRY", "R101", "R102"],
                "bottlenecks": ["narrow corridor between R101 and nursing station"],
                "equipment_issues": ["crash cart too far from R104"],
                "dead_zones": ["utility_support area rarely visited"],
                "efficiency_score": 6,
                "notes": "Synthetic swarm agent",
                "agent_index": i,
            }
            for i, role in enumerate(AGENT_ROLES * agents_per_role)
        ]
        return _aggregate(synthetic, facility_name)

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    scene_summary = _summarize_scene_graph(scene_graph)

    tasks = [
        _run_agent(client, role, scene_summary, facility_name, idx)
        for idx, role in enumerate(AGENT_ROLES * agents_per_role)
    ]
    results = await asyncio.gather(*tasks)
    return _aggregate(list(results), facility_name)
