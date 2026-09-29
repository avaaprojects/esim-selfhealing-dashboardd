"""One estate, joined on the eUICC id.

The dashboard has two halves that were only meeting on the Input -> Output
path:

* the **registry** under `data/` - who the client is, which group a device is
  in, its label, ICCID, profile, network and RSP environment (`datasets.py`);
* the **live agent session** - eUICC state, telemetry, incidents, actions
  (`agent_service.py`).

Both are keyed by the same eUICC id, so this module joins them once and hands
the result to every screen. Incidents, devices, telemetry and reports then name
the same client and the same device label as the Input and Output screens,
instead of each showing a bare 17-digit number.

Nothing new is invented here and nothing is duplicated: `context_for` is a
lookup in the registry CSVs, `run_for` is a lookup in the session's own record
of processed inputs. A device that is not in the registry (an ad-hoc scenario
eUICC) simply has no context, and the UI falls back to the id - it is never
given a made-up client.

No FastAPI imports: importable and testable on its own.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from . import datasets


def _index() -> Dict[str, Dict[str, Any]]:
    """eUICC id -> registry context. Empty if the registry cannot be read.

    A missing or tampered registry must not take the incident list down with
    it: the Input screen is where that is reported, and it checks integrity
    properly. Here we degrade to "no context".
    """
    try:
        reg = datasets.registry()
    except Exception:                                    # noqa: BLE001 - advisory join only
        return {}

    clients = {c["client_id"]: c for c in reg.get("clients", [])}
    groups = {g["group_id"]: g for g in reg.get("groups", [])}
    networks = {n["network_id"]: n for n in reg.get("networks", [])}
    rsp = {r["rsp_env_id"]: r for r in reg.get("rsp_environments", [])}

    out: Dict[str, Dict[str, Any]] = {}
    for d in reg.get("devices", []):
        client = clients.get(d.get("client_id")) or {}
        group = groups.get(d.get("group_id")) or {}
        net = networks.get(d.get("network_id")) or {}
        env = rsp.get(d.get("rsp_env_id")) or {}
        out[d["euicc_id"]] = {
            "client_id": client.get("client_id"),
            "client_name": client.get("name"),
            "group_id": group.get("group_id"),
            "group_name": group.get("name"),
            "device_label": d.get("device_label"),
            "cell_id": d.get("cell_id"),
            "origin": d.get("origin"),
            "iccid": d.get("iccid"),
            "eid": d.get("eid"),
            "profile_name": d.get("profile_name"),
            "fleet_size": d.get("fleet_size"),
            "network_id": net.get("network_id"),
            "network_name": net.get("name"),
            "plmn": net.get("plmn"),
            "auth_method": (net.get("auth") or {}).get("method"),
            "rsp_env_id": env.get("rsp_env_id"),
            "rsp_env_name": env.get("name"),
            "source_file": d.get("source_file"),
        }
    return out


def context_for(euicc_id: Optional[str], index: Optional[Dict[str, Any]] = None
                ) -> Optional[Dict[str, Any]]:
    """Registry context for one eUICC, or None if it is not a registered device."""
    if not euicc_id:
        return None
    return (index if index is not None else _index()).get(euicc_id)


def label_for(euicc_id: Optional[str], index: Optional[Dict[str, Any]] = None) -> str:
    """How to name a device in one line: its label, else the bare id."""
    ctx = context_for(euicc_id, index)
    return (ctx or {}).get("device_label") or (euicc_id or "unknown device")


def run_for(session: Any, incident_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """The processed input (Input -> Output) an incident came out of, if any.

    This is what lets an incident found on the Incidents screen link back to
    the Output screen that explains it.
    """
    if not incident_id:
        return None
    for run_id, run in session.input_runs.items():
        if incident_id in run.get("incident_ids", []):
            return {"run_id": run_id, "mode": run.get("mode"),
                    "dataset_id": run.get("dataset_id"),
                    "dataset_title": run.get("dataset_title")}
    return None


# -- enrichment applied by the routes ---------------------------------------
def attach_to_devices(devices: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add `context` to each device row. Registry order is not imposed: the
    session's own ordering (most open incidents first) is left alone."""
    index = _index()
    items = list(devices)
    for d in items:
        d["context"] = context_for(d.get("euicc_id"), index)
    return items


def attach_to_incidents(session: Any, incidents: Iterable[Dict[str, Any]]
                        ) -> List[Dict[str, Any]]:
    """Add `context` (client / device) and `run` (the processed input) to each
    incident, so every screen names an incident the same way."""
    index = _index()
    items = list(incidents)
    for inc in items:
        euicc_id = (inc.get("observation") or {}).get("euicc_id")
        inc["context"] = context_for(euicc_id, index)
        inc["run"] = run_for(session, inc.get("incident_id"))
    return items


def attach_to_incident(session: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """The same for one incident's full trace."""
    euicc_id = ((payload.get("incident") or {}).get("observation") or {}).get("euicc_id")
    payload["context"] = context_for(euicc_id)
    payload["run"] = run_for(session, (payload.get("incident") or {}).get("incident_id"))
    return payload
