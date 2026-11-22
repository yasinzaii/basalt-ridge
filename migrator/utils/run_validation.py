import json
from pathlib import Path


def validate_run(directory: Path, manifest: dict) -> dict:
    issues = []
    counts = {}

    def issue(resource, source_id, field, reason):
        issues.append({"resource": resource, "sourceId": source_id, "field": field, "reason": reason})

    def read(stage, resource):
        path = directory / stage / f"{resource}.json"
        if manifest["stages"][stage]["status"] != "completed":
            return []
        records = json.loads(path.read_text(encoding="utf-8"))
        counts[resource] = len(records)
        return records

    def index(resource, records):
        result = {}
        for record in records:
            key = record["sourceId"]
            if key is None:
                issue(resource, None, "sourceId", "Source identity unavailable")
            elif key in result:
                issue(resource, key, "sourceId", "Duplicate source identity")
            else:
                result[key] = record
        return result

    clients = index("clients", read("clients", "clients"))
    appointments = index("appointments", read("appointments", "appointments"))
    notes = index("notes", read("notes", "notes"))
    team = read("practice", "team")
    index("team", team)
    location_records = read("practice", "locations")
    service_records = read("practice", "services")
    locations = index("locations", location_records)
    services = index("services", service_records)
    payer_records = read("practice", "payers")
    index("payers", payer_records)
    for resource, records, payload_key in (
        ("team", team, "teamMember"),
        ("locations", location_records, "location"),
        ("services", service_records, "service"),
        ("payers", payer_records, "payer"),
    ):
        for record in records:
            for field, value in record[payload_key].items():
                if value is None:
                    issue(resource, record["sourceId"], field, "Unknown or unset extracted field")
    practitioners = {}
    for record in team:
        practitioner_id = record["sourceRefs"]["practitionerId"]
        if practitioner_id is not None:
            practitioners.setdefault(practitioner_id, []).append(record)
    for key, matches in practitioners.items():
        if len(matches) > 1:
            issue("team", key, "sourceRefs.practitionerId", "Ambiguous practitioner identity")

    def reference(resource, key, field, value, targets):
        if value is None:
            issue(resource, key, field, "Unresolved source reference")
        elif value not in targets:
            issue(resource, key, field, "Referenced source record is absent from this run; check coverage")

    for key, record in appointments.items():
        appointment = record["appointment"]
        for client_id in appointment["clientIds"]:
            reference("appointments", key, "clientIds", client_id, clients)
        reference("appointments", key, "clinicianId", appointment["clinicianId"], practitioners)
        for field, targets, hint in (("serviceId", services, "serviceName"),
                                     ("locationId", locations, "locationName")):
            if appointment[field] is not None or record["sourceRefs"].get(hint):
                reference("appointments", key, field, appointment[field], targets)
        if appointment["status"] is None:
            issue("appointments", key, "status", "Status unknown")

    for key, record in notes.items():
        note = record["note"]
        reference("notes", key, "clientId", note["clientId"], clients)
        # Do not equate user and practitioner IDs without source evidence.
        if note["authorId"] is not None:
            issue("notes", key, "authorId", "Author ID namespace needs verification before team matching")
        else:
            issue("notes", key, "authorId", "Author unresolved; a name is only a lookup hint")
        if note["appointmentId"] is not None:
            reference("notes", key, "appointmentId", note["appointmentId"], appointments)
            parent = appointments.get(note["appointmentId"])
            if parent and note["clientId"] not in parent["appointment"]["clientIds"]:
                issue("notes", key, "appointmentId", "Note patient is not on the referenced appointment")
        for field in ("dateOfService", "type", "status"):
            if note[field] is None:
                issue("notes", key, field, "Required import value unresolved")
        if note["status"] == "signed" and note["signedAt"] is None:
            issue("notes", key, "signedAt", "Signing timestamp unavailable")

    limitations = {}
    for name, state in manifest["stages"].items():
        if state["status"] == "completed":
            report = json.loads((directory / name / "report.json").read_text(encoding="utf-8"))
            if report["limitations"]:
                limitations[name] = report["limitations"]
            for record_id, fields in report.get("missing_fields", {}).items():
                if fields:
                    issue(name, record_id, ", ".join(fields), "Unknown extracted fields")
            for field in report.get("missing_practice_fields", []):
                issue("practice", None, field, "Unknown practice field")
        else:
            limitations[name] = [state["status"]]
    return {
        "status": "needs_review" if issues or limitations else "passed",
        "counts": counts, "issues": issues, "stage_limitations": limitations,
        "scope": "Source relationship checks only; no IDs changed, no source fidelity or API readiness claim.",
    }
