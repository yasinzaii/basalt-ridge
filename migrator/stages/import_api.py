import json
import os
from datetime import datetime

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from migrator.utils.files import read_json, write_json
from migrator.utils.comparison import check_payload, matches_submitted_fields, non_null

KINDS = (
    "team", "locations", "services", "payers", "clients", "appointments", "notes",
)
STAGE_FILES = {
    "practice": ("practice", "practice"),
    "team": ("practice", "team"),
    "locations": ("practice", "locations"),
    "services": ("practice", "services"),
    "payers": ("practice", "payers"),
    "clients": ("clients", "clients"),
    "appointments": ("appointments", "appointments"),
    "notes": ("notes", "notes"),
}
WRAPPERS = {"team": "teamMember", "locations": "location", "services": "service", "payers": "payer", "clients": "client", "appointments": "appointment", "notes": "note"}


class ApiError(RuntimeError):
    pass


class CarepatronAPI:
    def __init__(self, base_url: str, email: str, password: str):
        self.url = base_url.rstrip("/")
        self.token = None
        self.token = self.request("POST", "/auth/login", {"email": email, "password": password})["token"]

    def request(self, method: str, path: str, body: dict | None = None):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, allow_nan=False).encode("utf-8")

        request = Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=12) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            details = exc.read(4096).decode("utf-8", errors="replace")
            raise ApiError(f"{method} {path}: HTTP {exc.code}: {details}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise ApiError(f"{method} {path}: uncertain network result ({exc}); inspect target before retrying") from None

    def create(self, kind: str, payload: dict):
        return self.request("POST", "/" + kind, payload)

    def get(self, kind: str, identifier: str):
        return self.request("GET", f"/{kind}/{identifier}")


def _check_returned(payload: dict, returned: dict, label: str) -> None:
    if not isinstance(returned.get("id"), str) or not returned["id"]:
        raise ApiError(f"{label}: API did not return an ID")
    for field, value in payload.items():
        if field not in returned or not matches_submitted_fields(field, value, returned[field]):
            raise ApiError(f"{label}: API response differs at {field}")


def _read_input(run_dir: Path):
    manifest = read_json(run_dir / "manifest.json")
    if not manifest.get("source"):
        raise ValueError("Extraction manifest must identify the source")
    for stage in ("practice", "clients", "appointments", "notes"):
        if manifest.get("stages", {}).get(stage, {}).get("status") != "completed":
            raise ValueError(f"Extraction stage is not complete: {stage}")
    return {kind: read_json(run_dir / stage / (name + ".json")) for kind, (stage, name) in STAGE_FILES.items()}


def import_run(run_dir: Path, api_url: str = "http://127.0.0.1:4000/api/v1", *,
               email: str | None = None, password: str | None = None) -> dict:
    """Import an extraction run using in-memory source-to-destination IDs."""
    run_dir = run_dir.resolve()
    data = _read_input(run_dir)
    ids = {kind: {} for kind in KINDS}
    warnings = []
    api = CarepatronAPI(api_url, email or os.environ.get("CAREPATRON_EMAIL", "you@practice.example"),
                        password or os.environ.get("CAREPATRON_PASSWORD", "carepatron"))
    owner = api.request("GET", "/me")

    def warn(message: str):
        warnings.append(message)

    payload = non_null(data["practice"])
    updated = api.request("PATCH", "/practice", payload)
    for field, value in payload.items():
        if field not in updated or not matches_submitted_fields(field, value, updated[field]):
            raise ApiError(f"Practice update mismatch: {field}")

    # Map the extracted owner to the mock's EXISTING owner. Never POST an owner
    # and never change the mock account's login email to an unverified address.
    owners = [r for r in data["team"] if r["teamMember"].get("role") == "owner"]
    if len(owners) > 1:
        raise ValueError("More than one source owner; cannot choose a destination owner")
    if owners:
        source_owner = owners[0]
        src_id = source_owner["sourceId"]
        if src_id is None:
            raise ValueError("Source owner needs a stable source ID for appointment links")
        payload = non_null({k: v for k, v in source_owner["teamMember"].items() if k not in ("email", "role")})
        result = api.request("PATCH", f"/team/{owner['id']}", payload)
        _check_returned(payload, result, "Owner")
        ids["team"][src_id] = owner["id"]
        if source_owner["teamMember"].get("email") != owner["email"]:
            warn("Source owner email was not imported; the mock login email was retained")

    for kind in ("team", "locations", "services", "payers", "clients"):
        for record in data[kind]:
            source_id = record["sourceId"]
            if kind == "team" and record["teamMember"].get("role") == "owner":
                continue
            if not source_id:
                warn(f"{kind}: skipped record with missing sourceId")
                continue
            payload = non_null(record[WRAPPERS[kind]])
            if kind == "team":
                if not payload.get("email") or payload["email"] == "unavailable@example.com":
                    warn(f"team {source_id}: missing/unverified email; skipped")
                    continue
                if "role" not in payload or "status" not in payload:
                    warn(f"team {source_id}: unknown role/status; skipped")
                    continue
            if kind == "services":
                if "rate" not in payload:
                    warn(f"services {source_id}: rate unknown; skipped instead of inventing 0")
                    continue
                if "modifiers" not in payload:
                    warn(f"service {source_id}: modifiers unknown; API defaults to empty list")
            if kind == "payers" and "type" not in payload:
                warn(f"payer {source_id}: type unknown; skipped instead of defaulting to commercial")
                continue
            if kind == "clients":
                if "createdAt" not in payload:
                    warn(f"client {source_id}: original creation date unknown; skipped instead of using today")
                    continue
                for collection in ("diagnoses", "contacts"):
                    if collection not in payload:
                        warn(f"client {source_id}: {collection} unknown; destination defaults to empty list")
                clinician_id = payload.get("primaryClinicianId")
                if clinician_id is not None:
                    # Extracted clients must never contain destination IDs.
                    raise ValueError(f"client {source_id}: unexpected primaryClinicianId; needs source mapping")
                if "status" not in payload:
                    warn(f"client {source_id}: destination defaults status to active (unknown in source)")
                if "billingType" not in payload:
                    warn(f"client {source_id}: destination defaults billingType to self_pay (unknown in source)")
            check_payload(kind, payload)
            result = api.create(kind, payload)
            _check_returned(payload, result, f"{kind} {source_id}")
            _check_returned(payload, api.get(kind, result["id"]), f"{kind} {source_id} readback")
            ids[kind][source_id] = result["id"]

    practitioners = {}
    for member in data["team"]:
        source_id = member["sourceId"]
        practitioner = member["sourceRefs"].get("practitionerId")
        if source_id in ids["team"] and practitioner:
            practitioners[practitioner] = ids["team"][source_id]

    for record in data["appointments"]:
        source_id = record["sourceId"]
        src = record["appointment"]
        clients = [ids["clients"].get(s) for s in src["clientIds"]]
        clinician = practitioners.get(src["clinicianId"])
        if not clinician or any(c is None for c in clients):
            warn(f"appointment {source_id}: unresolved practitioner or client; skipped")
            continue
        payload = non_null(src)
        payload["clientIds"] = clients
        payload["clinicianId"] = clinician
        for field, kind, hint in (("serviceId", "services", "serviceName"), ("locationId", "locations", "locationName")):
            src_ref = src[field]
            payload[field] = ids[kind].get(src_ref) if src_ref else None
            if src_ref and payload[field] is None:
                raise ValueError(f"appointment {source_id}: {field} source ID not imported")
            if not src_ref and record["sourceRefs"].get(hint):
                warn(f"appointment {source_id}: {field} unresolved; imported as null")
        if src["status"] is None:
            warn(f"appointment {source_id}: status unknown; destination defaults to scheduled")
        check_payload("appointments", payload)
        result = api.create("appointments", payload)
        _check_returned(payload, result, f"appointment {source_id}")
        _check_returned(payload, api.get("appointments", result["id"]), f"appointment {source_id} readback")
        ids["appointments"][source_id] = result["id"]

    for record in data["notes"]:
        source_id = record["sourceId"]
        src = record["note"]
        client_id = ids["clients"].get(src["clientId"])
        if not client_id:
            warn(f"note {source_id}: client missing; skipped")
            continue
        payload = non_null(src)
        payload["clientId"] = client_id
        if src.get("appointmentId") is not None:
            target_id = ids["appointments"].get(src["appointmentId"])
            if not target_id:
                warn(f"note {source_id}: appointment unresolved; skipped")
                continue
            payload["appointmentId"] = target_id
        author_id = ids["team"].get(src.get("authorId"))
        if not author_id:
            warn(f"note {source_id}: author source ID unresolved; skipped")
            continue
        payload["authorId"] = author_id
        if "dateOfService" not in payload:
            payload["dateOfService"] = datetime.now().astimezone().date().isoformat()
            warn(f"note {source_id}: service date missing; current date {payload['dateOfService']} substituted")
        if "status" not in payload:
            warn(f"note {source_id}: status unknown; destination defaults to draft")
        if "type" not in payload:
            warn(f"note {source_id}: type unknown; destination defaults to progress")
        if payload.get("status") == "signed" and "signedAt" not in payload:
            warn(f"note {source_id}: signed status without signing timestamp; skipped")
            continue
        check_payload("notes", payload)
        result = api.create("notes", payload)
        _check_returned(payload, result, f"note {source_id}")
        _check_returned(payload, api.get("notes", result["id"]), f"note {source_id} readback")
        ids["notes"][source_id] = result["id"]

    warn("insurance policies: extraction stage not implemented; nothing imported")
    report = {"status": "completed_with_limitations" if warnings else "completed",
              "counts": {kind: len(ids[kind]) for kind in KINDS},
              "warnings": warnings,
              "scope": "Mock API import. Warnings describe unresolved source details."}
    folder = run_dir / "import"
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "report.json", report)
    return report
