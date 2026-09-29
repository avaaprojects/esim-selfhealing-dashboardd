"""Deployment settings: the few numbers a team may want to change.

Read from `config.json` in the project root (or wherever `DASHBOARD_CONFIG`
points) and, for individual values, from environment variables. Every setting
has a working default, so the file is optional.

    {
      "severity": {
        "high_ratio": 4.0,
        "medium_ratio": 1.5,
        "shared_profile_raises": true,
        "unresolved_raises": true
      }
    }

Only the severity rules live here for now: they are the judgement most likely
to differ between teams, and nothing else in the loop is a tunable opinion (the
detector and safety envelope are the agent's own configuration, in
`esim_selfhealing/`). A bad value is reported and the default is used, rather
than taking the dashboard down at import time.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config.json"

DEFAULTS: Dict[str, Any] = {
    "severity": {
        "high_ratio": 4.0,            # anomaly score >= this x threshold -> starts at "high"
        "medium_ratio": 1.5,          # ...>= this -> starts at "medium"; below -> "low"
        "shared_profile_raises": True,   # +1 level when more than one device shares the profile
        "unresolved_raises": True,       # +1 level when the agent did not resolve it
    },
}

#: environment overrides, per setting
_ENV = {
    ("severity", "high_ratio"): ("SEVERITY_HIGH_RATIO", float),
    ("severity", "medium_ratio"): ("SEVERITY_MEDIUM_RATIO", float),
    ("severity", "shared_profile_raises"): ("SEVERITY_SHARED_PROFILE_RAISES", bool),
    ("severity", "unresolved_raises"): ("SEVERITY_UNRESOLVED_RAISES", bool),
}

_lock = threading.Lock()
_cache: Dict[str, Any] | None = None
_problems: list[str] = []


def _as_bool(text: str) -> bool:
    return str(text).strip().lower() in ("1", "true", "yes", "on")


def _merge(base: Dict[str, Any], over: Dict[str, Any], problems: list[str], path: str = "") -> Dict[str, Any]:
    out = dict(base)
    for key, value in (over or {}).items():
        where = f"{path}{key}"
        if key.startswith("_"):
            continue                          # a comment key, e.g. "_comment"
        if key not in base:
            problems.append(f"{where}: unknown setting, ignored")
            continue
        if isinstance(base[key], dict):
            out[key] = _merge(base[key], value if isinstance(value, dict) else {}, problems, where + ".")
        elif isinstance(base[key], bool):
            out[key] = bool(value)
        elif isinstance(base[key], float):
            try:
                out[key] = float(value)
            except (TypeError, ValueError):
                problems.append(f"{where}: '{value}' is not a number, using {base[key]}")
        else:
            out[key] = value
    return out


def load(path: Any = None) -> Dict[str, Any]:
    """The settings, cached. `reload()` picks up a changed file."""
    global _cache, _problems
    with _lock:
        if _cache is not None and path is None:
            return _cache
        problems: list[str] = []
        cfg = json.loads(json.dumps(DEFAULTS))                 # deep copy
        config_path = Path(path or os.environ.get("DASHBOARD_CONFIG") or DEFAULT_CONFIG_PATH)
        if config_path.is_file():
            try:
                cfg = _merge(cfg, json.loads(config_path.read_text()), problems)
            except (json.JSONDecodeError, OSError) as exc:
                problems.append(f"{config_path.name}: {exc}; using defaults")
        for (section, key), (env_var, kind) in _ENV.items():
            raw = os.environ.get(env_var)
            if raw is None:
                continue
            try:
                cfg[section][key] = _as_bool(raw) if kind is bool else kind(raw)
            except (TypeError, ValueError):
                problems.append(f"{env_var}: '{raw}' is not valid, ignored")
        if cfg["severity"]["medium_ratio"] > cfg["severity"]["high_ratio"]:
            problems.append("severity.medium_ratio is above high_ratio; using the defaults for both")
            cfg["severity"]["high_ratio"] = DEFAULTS["severity"]["high_ratio"]
            cfg["severity"]["medium_ratio"] = DEFAULTS["severity"]["medium_ratio"]
        if path is None:
            _cache, _problems = cfg, problems
        return cfg


def reload() -> Dict[str, Any]:
    global _cache
    with _lock:
        _cache = None
    return load()


def problems() -> list[str]:
    load()
    return list(_problems)


def severity_rules() -> Dict[str, Any]:
    return load()["severity"]
