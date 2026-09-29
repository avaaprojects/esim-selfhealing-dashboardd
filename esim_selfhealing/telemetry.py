"""Synthetic telemetry source standing in for the RAN + core + eUICC feeds.

Produces the same 5-dimensional x_t the MONITOR stage expects, so the rest of
the pipeline is unchanged when a real Kafka/OTLP consumer replaces this class.

Fault scenarios are injectable so each use case can reproduce a specific
failure mode deterministically (fixed seed).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator, List, Optional

import numpy as np

from .schemas import FEATURE_DIM, Observation

#: Healthy operating point, ordered per schemas.FEATURE_NAMES.
NOMINAL_MEAN = np.array([0.8, -92.0, 0.015, 120.0, 0.010])
NOMINAL_STD = np.array([0.30, 2.50, 0.006, 18.0, 0.005])

#: Additive fault signatures. Each maps a fault class to a delta on x_t.
FAULT_SIGNATURES = {
    # Corrupted ISD-P: AKA fails hard, OTA sessions fail, radio is fine.
    "isdp_corruption": np.array([9.0, 0.0, 0.05, 40.0, 0.09]),
    # SM-DP+ session outage: OTA fails and latency spikes, AKA mostly fine.
    "smdp_session_outage": np.array([1.2, 0.0, 0.01, 480.0, 0.30]),
    # Radio degradation: RSRP collapses, drops rise, no OTA signature.
    "radio_degradation": np.array([1.0, -22.0, 0.22, 60.0, 0.005]),
    # Key desync between eUICC and SM-SR: AKA failures only - the profile is
    # intact, so OTA downloads still complete and latency is unaffected.
    "key_desync": np.array([13.0, 0.0, 0.02, 4.0, 0.0]),
}


# ---- CLASS: FaultWindow ----
@dataclass
class FaultWindow:
    """Inject `fault` between sample indices [start, end)."""

    fault: str
    start: int
    end: int
    ramp: bool = False   # linearly ramp the signature in (slow-onset fault)


# ---- CLASS: TelemetryStream ----
class TelemetryStream:
    """Deterministic generator of Observation objects for one eUICC."""

    # ---- METHOD: TelemetryStream.__init__ ----
    def __init__(
        self,
        euicc_id: str = "89330000000048213",
        cell_id: str = "CELL-4471",
        n_samples: int = 400,
        faults: Optional[List[FaultWindow]] = None,
        drift_per_sample: float = 0.0,
        period_s: float = 1.0,
        seed: int = 42,
        t0: Optional[float] = None,
    ) -> None:
        self.euicc_id = euicc_id
        self.cell_id = cell_id
        self.n_samples = n_samples
        self.faults = faults or []
        self.drift_per_sample = drift_per_sample
        self.period_s = period_s
        self.rng = np.random.default_rng(seed)
        self.t0 = t0 if t0 is not None else time.time()

    # -- internals ---------------------------------------------------------
    # ---- METHOD: TelemetryStream._active_fault ----
    def _active_fault(self, i: int) -> tuple[Optional[str], float]:
        for w in self.faults:
            if w.start <= i < w.end:
                if w.ramp:
                    span = max(1, w.end - w.start)
                    return w.fault, (i - w.start + 1) / span
                return w.fault, 1.0
        return None, 0.0

    # ---- METHOD: TelemetryStream._sample ----
    def _sample(self, i: int) -> Observation:
        x = NOMINAL_MEAN + self.rng.normal(0.0, NOMINAL_STD, size=FEATURE_DIM)

        # Slow baseline drift (diurnal load, firmware rollout) the EWMA should
        # absorb WITHOUT opening an incident.
        x = x + self.drift_per_sample * i * np.array([0.02, -0.03, 0.0002, 0.6, 0.0001])

        fault, scale = self._active_fault(i)
        if fault is not None:
            x = x + scale * FAULT_SIGNATURES[fault]

        # Physical clipping.
        x[0] = max(0.0, x[0])           # AKA failure rate
        x[2] = float(np.clip(x[2], 0.0, 1.0))
        x[3] = max(1.0, x[3])
        x[4] = float(np.clip(x[4], 0.0, 1.0))

        return Observation(
            ts=self.t0 + i * self.period_s,
            euicc_id=self.euicc_id,
            cell_id=self.cell_id,
            features=x.tolist(),
            ground_truth_fault=fault,
        )

    # -- public API --------------------------------------------------------
    # ---- METHOD: TelemetryStream.__iter__ ----
    def __iter__(self) -> Iterator[Observation]:
        for i in range(self.n_samples):
            yield self._sample(i)

    # ---- METHOD: TelemetryStream.collect ----
    def collect(self) -> List[Observation]:
        return list(self)


# ---- FUNCTION: healthy_stream ----
def healthy_stream(n: int = 200, seed: int = 1) -> TelemetryStream:
    return TelemetryStream(n_samples=n, seed=seed)


# ---- FUNCTION: scenario_isdp_corruption ----
def scenario_isdp_corruption(seed: int = 42) -> TelemetryStream:
    """Clean baseline, then a sudden ISD-P corruption at sample 250."""
    return TelemetryStream(
        n_samples=300,
        faults=[FaultWindow("isdp_corruption", start=250, end=300)],
        drift_per_sample=1.0,   # slow drift the detector must NOT flag
        seed=seed,
    )


# ---- FUNCTION: scenario_slow_radio_drift ----
def scenario_slow_radio_drift(seed: int = 43) -> TelemetryStream:
    """Slow-onset radio degradation - tests ramp sensitivity."""
    return TelemetryStream(
        n_samples=320,
        faults=[FaultWindow("radio_degradation", start=200, end=320, ramp=True)],
        seed=seed,
    )


# ---- FUNCTION: scenario_smdp_outage ----
def scenario_smdp_outage(seed: int = 44) -> TelemetryStream:
    return TelemetryStream(
        n_samples=300,
        faults=[FaultWindow("smdp_session_outage", start=240, end=300)],
        seed=seed,
    )
