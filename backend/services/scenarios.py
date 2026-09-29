"""The simulation catalogue exposed at /api/simulation.

Every entry is a real `TelemetryStream` from `esim_selfhealing.telemetry`, or a
small composition of them, so a scenario card in the UI runs the same code path
the console use cases in `usecases/` run. Nothing here is mocked.

`shared_fleet` and `night_shift` need inventory set up on the RSP client before
the stream is consumed (a profile shared across N devices multiplies PLAN's
blast radius), which is what `fleet` expresses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from esim_selfhealing.schemas import Observation
from esim_selfhealing.telemetry import (
    FaultWindow,
    TelemetryStream,
    scenario_isdp_corruption,
    scenario_slow_radio_drift,
    scenario_smdp_outage,
)


#: Ordered simulation categories shown on the Simulation screen. Each entry is
#: what that group of scenarios is testing, not decoration - the category a
#: scenario is assigned to below determines which pipeline stage it stresses.
CATEGORY_ORDER: List[Dict[str, str]] = [
    {"key": "detection", "label": "Detection & Monitoring",
     "blurb": "Does MONITOR's EWMA/chi-square detector separate real faults from drift?"},
    {"key": "diagnosis", "label": "Diagnosis & Reasoning",
     "blurb": "Does REASON identify the true failure source instead of reacting to the alert text?"},
    {"key": "planning_safety", "label": "Planning & Safety / Gated Output",
     "blurb": "Does PLAN pick a sound remediation, and does the SAFETY envelope block what it should?"},
    {"key": "end_to_end", "label": "End-to-End / Whole Estate",
     "blurb": "Does the full loop hold up across many devices and failure modes at once?"},
]


@dataclass(frozen=True)
class Scenario:
    key: str
    name: str
    description: str
    expectation: str
    fault_class: str
    streams: Callable[[], List[TelemetryStream]]
    #: euicc_id -> number of devices sharing the profile, applied before the run.
    fleet: Dict[str, int] = field(default_factory=dict)
    use_case: str = ""
    #: key into CATEGORY_ORDER - which capability this scenario is testing.
    category: str = "detection"


def _single(factory: Callable[[], TelemetryStream]) -> Callable[[], List[TelemetryStream]]:
    """Wrap a stream factory, not a stream instance.

    `TelemetryStream` owns a stateful `np.random.Generator`, so iterating the
    *same* instance twice yields different samples. Every scenario therefore
    builds a fresh stream per run, which is what makes a given scenario key
    reproducible across clicks of RUN SELF-HEALING.
    """
    return lambda: [factory()]


def _key_desync_stream() -> List[TelemetryStream]:
    return [TelemetryStream(
        euicc_id="89330000000077145",
        cell_id="CELL-4471",
        n_samples=300,
        faults=[FaultWindow("key_desync", start=240, end=300)],
        drift_per_sample=1.0,
        seed=45,
    )]


def _shared_fleet_stream() -> List[TelemetryStream]:
    return [TelemetryStream(
        euicc_id="89330000000090031",
        cell_id="CELL-6602",
        n_samples=300,
        faults=[FaultWindow("isdp_corruption", start=240, end=300)],
        drift_per_sample=1.0,
        seed=46,
    )]


def _night_shift_streams() -> List[TelemetryStream]:
    """Five devices, five failure modes - the uc6 estate."""
    plan: List[Tuple[str, str, str, int]] = [
        ("89330000000048213", "CELL-4471", "isdp_corruption", 42),
        ("89330000000051887", "CELL-2210", "smdp_session_outage", 44),
        ("89330000000063902", "CELL-8814", "radio_degradation", 43),
        ("89330000000077145", "CELL-4471", "key_desync", 45),
        ("89330000000090031", "CELL-6602", "isdp_corruption", 46),
    ]
    return [
        TelemetryStream(
            euicc_id=euicc, cell_id=cell, n_samples=300,
            faults=[FaultWindow(fault, start=240, end=300)],
            drift_per_sample=1.0, seed=seed,
        )
        for euicc, cell, fault, seed in plan
    ]


CATALOGUE: Dict[str, Scenario] = {
    s.key: s for s in [
        Scenario(
            key="isdp_corruption",
            name="ISD-P corruption",
            description=(
                "A clean overnight baseline with slow firmware drift, then a sudden "
                "profile checksum mismatch at sample 250. The detector has to absorb "
                "the drift and still catch the real fault."
            ),
            expectation="Expect PROFILE_REPUSH, admissible, AUTO-REMEDIATED.",
            fault_class="isdp_corruption",
            streams=_single(scenario_isdp_corruption),
            use_case="uc1 / uc2",
            category="detection",
        ),
        Scenario(
            key="smdp_outage",
            name="SM-DP+ session outage",
            description=(
                "OTA latency spikes and SM-DP+ sessions start timing out while AKA "
                "stays broadly healthy. Looks like a profile fault in the alert text; "
                "isn't one."
            ),
            expectation="Expect BEARER_FAILOVER rather than a re-push.",
            fault_class="smdp_session_outage",
            streams=_single(scenario_smdp_outage),
            use_case="uc2",
            category="diagnosis",
        ),
        Scenario(
            key="slow_radio_drift",
            name="Slow radio degradation",
            description=(
                "RSRP collapses gradually over 120 samples with rising session drops "
                "and no OTA signature - a ramped fault rather than a step change."
            ),
            expectation="Expect a radio diagnosis, not a profile-layer action.",
            fault_class="radio_degradation",
            streams=_single(scenario_slow_radio_drift),
            use_case="uc1",
            category="detection",
        ),
        Scenario(
            key="key_desync",
            name="eUICC / SM-SR key desync",
            description=(
                "AKA authentication fails hard while OTA downloads still complete and "
                "latency is untouched. The profile is intact; the session keys are not."
            ),
            expectation="Expect KEY_ROTATION to be considered against its risk bound.",
            fault_class="key_desync",
            streams=_key_desync_stream,
            use_case="uc2",
            category="diagnosis",
        ),
        Scenario(
            key="shared_fleet",
            name="Shared-profile fleet",
            description=(
                "The same ISD-P corruption, but on a profile shared by 120 logistics "
                "devices. The diagnosis is identical; the blast radius is not."
            ),
            expectation="Expect the envelope to refuse autonomous dispatch on B_max.",
            fault_class="isdp_corruption",
            streams=_shared_fleet_stream,
            fleet={"89330000000090031": 120},
            use_case="uc3 / uc4",
            category="planning_safety",
        ),
        Scenario(
            key="night_shift",
            name="Unattended night shift",
            description=(
                "Five devices, five failure modes, one shift, nobody watching the NOC "
                "console. Algorithm 1 end to end across the whole estate."
            ),
            expectation="Expect a mix of auto-remediated, queued and escalated outcomes.",
            fault_class="mixed",
            streams=_night_shift_streams,
            fleet={"89330000000090031": 120},
            use_case="uc6",
            category="end_to_end",
        ),
    ]
}

DEFAULT_SCENARIO = "isdp_corruption"


def get(key: str) -> Optional[Scenario]:
    return CATALOGUE.get(key)


_CATEGORY_LABELS: Dict[str, str] = {c["key"]: c["label"] for c in CATEGORY_ORDER}


def category_label(key: str) -> str:
    return _CATEGORY_LABELS.get(key, key)


def observations(scenario: Scenario) -> Iterable[Observation]:
    for stream in scenario.streams():
        yield from stream
