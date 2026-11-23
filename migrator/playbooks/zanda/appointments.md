# Zanda appointments — sequential per-client extraction

Do not use Tools → Data Export, CSV, reports, or bulk export. Do not create,
edit, cancel, delete, or confirm appointments. Start with `browser_observe`.

## Enumerate and inspect

1. Navigate to **People → Search**. Filter to Client profiles and enumerate
   every result page, exactly as in `clients.md`. Visit clients one at a time.
2. Open the client's profile and select **Appointments**. Turn off any
   **Show only Future Appointments** filter. Inspect all visible pages and
   include past and future appointments plus retained cancellations, late
   cancellations, and no-shows. Do not restore deleted records.
3. Open each appointment's read-only detail view. Record its stable appointment
   ID from a labelled field or verified detail URL, the associated client ID,
   practitioner/calendar, service, location, start/end, status, comments, and
   recurrence information when explicitly displayed.
4. Finish one client's appointment list before moving to the next. If a group
   appointment appears under multiple client profiles, combine participants
   only when the same explicit appointment ID verifies the match. Deduplicate
   only by that ID.

## Destination mapping

Return each appointment in `records` as
`{ "sourceId": "<Zanda appointment ID>", "appointment": {...},
"sourceRefs": {"clinicianName":..., "serviceName":..., "locationName":...} }`.

- Title or group name → `appointment.title`
- Start/end → `appointment.startsAt`, `appointment.endsAt`, ISO 8601 with an
  explicit offset
- Client IDs → `appointment.clientIds` as verified source ID strings; include
  every verified group participant
- Practitioner ID → `appointment.clinicianId` as the source practitioner ID.
  Call `load_records` with `stage="practice"` and use the matching team member's
  `sourceRefs.practitionerId` from the returned `team` records. If the account has exactly one verified practitioner,
  use that ID and report the assumption. Otherwise check **Settings → Team →
  Practitioners**. When the account shows exactly one practitioner, use that
  practitioner's observed source ID and report the single-practitioner
  assumption in `limitations`. If multiple practitioners are shown or the ID
  cannot be found, use null and report it. Never put a name in the ID field.
- Practitioner display name → `sourceRefs.clinicianName`
- Service name → `sourceRefs.serviceName`; set `appointment.serviceId` null
  unless an explicit service source ID is shown
- Location name → `sourceRefs.locationName`; set `appointment.locationId` null
  unless an explicit location source ID is shown
- Recurring-series ID and recurrence rule → `appointment.seriesId` and
  `appointment.recurrence` only when explicitly shown
- Comments → `appointment.memo`, copied verbatim

Use the account's explicitly recorded IANA business time zone to interpret
local appointment times and apply the correct offset for each date, including
daylight-saving changes. If that time zone is unavailable or ambiguous, do not
guess an offset; report and omit records whose timestamps cannot be represented.

Map explicit statuses as follows: completed → `completed`, cancelled →
`cancelled`, late cancellation → `late_cancelled`, no-show → `no_show`.
Pending/confirmed may map to `scheduled` only when they clearly denote a booked
appointment. `Arrived` is not `completed`; if it cannot be represented without
losing status meaning, use null for status and report it. Do not infer status
from appointment date, reminders, or presence on the calendar.

These are staged extraction records. `clientIds` and `clinicianId` are source
IDs, not Carepatron IDs. The importer must resolve them before API submission.
When shown, use source service/location IDs in `serviceId` and `locationId`;
the importer replaces them with Carepatron IDs. Otherwise use null. Omit records
missing a verified appointment ID, client IDs, or valid start/end and report them.

## Save each record

After completing each individual record, call `append_record` once with that
record as a JSON object encoded in the `record` string. Use the exact `records`
item shape described above, including destination field names and source IDs.
Before the final response call `load_records` with `stage="current"`, then return the entire loaded
list as `records` with your `limitations`. Report incomplete or omitted records;
do not invent values to fill required fields.

## Completion

Continue through every client and appointment page. Keep group membership
verified, preserve source IDs as strings, and report inaccessible profiles,
missing identifiers, ambiguous status/time zone, and any incomplete coverage
in `limitations`. Do not claim the run is complete until the final client has
been inspected.
