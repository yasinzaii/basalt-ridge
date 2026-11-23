# Zanda clinical notes — sequential per-client extraction

Do not use Tools → Data Export, CSV, reports, or bulk export. Do not create,
edit, unlock, complete, sign, or delete notes. Start with `browser_observe`.

## Enumerate and inspect

1. Navigate to **People → Search**. Filter to Client profiles and enumerate
   every result page. Visit clients one at a time.
2. Open each client's profile and navigate to **Records → Notes**. Inspect all
   note-list pages and include both Draft and Completed notes. Do not open
   deleted notes unless the user explicitly requests deleted records.
3. Expand each note card in the Notes list and read its title, Draft/Completed
   label, linked appointment and **Created by** identity when visible. The
   expanded card may show the note's form sections and their answers directly.
4. Read every displayed section heading and its complete answer, including
   sections such as **Progress (since last appointment)**, **Interventions
   provided**, **Between session practice**, and **Plan for next session**.
   Put the headings and answers together in `note.content` in their displayed
   order, preserving the visible wording and line breaks; do not summarize.
   Read all snapshot pages using `next_offset` when truncated.
5. If the expanded card lacks required details, inspect the note's detail view
   without changing any field. Do not click **Save as Draft**, **Save and
   Complete**, or any signing controls. If the text or metadata cannot be read,
   report the gap rather than inventing it. Finish one client's notes before
   moving to the next client.

## Destination mapping

Return each note as
`{ "sourceId": "<verified Zanda note ID or null>", "note": {...}, "sourceRefs":
{"authorName":..., "templateId":...} }`.

- Client profile ID → `note.clientId` as a source ID
- Linked appointment ID → `note.appointmentId` as a source ID only if the note
  explicitly links to it and the appointment includes this client
- Author → `note.authorId` as the source team user ID, not the practitioner
  profile ID. Before saving notes, call `load_records` with `stage="practice"`.
  In its `team` list, match the card's **Created by** email to
  `teamMember.email` and put that record's `sourceId` in `note.authorId`.
  Use the team user ID, not `sourceRefs.practitionerId`.
  If the team file is unavailable or the identity is unclear, check
  **Settings → Team → Users → User Management**. Preserve the
  displayed identity in `sourceRefs.authorName`. If no author is displayed and
  the account shows exactly one practitioner with a linked user ID, use that
  user ID and report the single-practitioner assumption in `limitations`.
  If an author is shown, resolve that identity instead. `note.authorId` must be
  a verified source user ID. If it cannot be resolved, report and omit the note.
- Template name → `note.template`; template ID → `sourceRefs.templateId`
- Note title → `note.title`
- Activity/service date → `note.dateOfService` only when explicitly shown as
  the service date, or when derived from the exact linked appointment
- Note state Draft → `note.status="draft"`
- Set `note.status="signed"` only when signing is explicitly established.
  A Completed/locked state alone does not establish a signature; use null and
  report it. Set `note.signedAt` only from an explicit signature timestamp.
- Created timestamp → `note.createdAt` only when explicitly shown, preserving
  its time zone offset
- Complete visible form content → one `note.content` string with section
  headings and answers in order. Preserve the visible text; do not invent HTML
  or claim that hidden formatting was captured.

Do not use note creation time as `dateOfService`. Do not infer `note.type`
from the note title or template ID. Map a type only if an explicit note type
is present and directly corresponds to `intake`, `progress`,
`treatment_plan`, `contact`, or `discharge`; otherwise use null and report that
it is unknown.

## Save each record

While each expanded note is still visible, copy the displayed section headings
and answers into `note.content` and call `append_record` before leaving the
note. The text shown directly on the expanded card is note content; it does not
require an edit view. Use `memory_load` if an earlier saved observation contains
the text. Load the Practice team records and resolve the author before saving.
If the source note ID cannot be verified, set `sourceId` to null and report it;
do not leave `note.authorId` null. Report if any section could not be read.
Never invent IDs or save an empty note body.

After completing each individual record, call `append_record` once with that
record as a JSON object encoded in the `record` string. Use the exact `records`
item shape described above, including destination field names and source IDs.
Before the final response call `load_records` with `stage="current"`, then return the entire loaded
list as `records` with your `limitations`. Report incomplete or omitted records;
do not invent values to fill required fields.

## Completion

Use source client and appointment IDs only for staging; these must be resolved
to Carepatron IDs before API submission. Preserve source note IDs separately;
never put them in the Carepatron note object. Report notes whose full body,
author, client, date, or appointment link cannot be verified. Continue through
every client and every note page before reporting complete coverage.
