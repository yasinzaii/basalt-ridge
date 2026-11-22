# Cliniko treatment notes CSV export

Use the signed-in fictional trial account. Start with `browser_observe`.
Use `save_result=false` unless a result needs to be retrieved later.

1. Navigate to **Settings → Data exports**.
2. Under **Data to export**, select **all treatment notes** (exact visible label).
   Keep **Spreadsheet (.csv)**; do not use a different export type.
3. Clear both date fields. Click the **From** textbox, then the enabled
   **Any time** button in the resulting snapshot. Repeat for **To**.
   Verify both fields are blank; never click a disabled calendar button.
4. Check **Include archived records** if the UI supports it; report uncertain
   archived coverage rather than assuming a checked box guarantees inclusion.
5. Note existing exports, then click **Export data** only once. Call
   `browser_wait` with `seconds=5` and repeat if still pending, without resubmitting.
6. Identify the new **all treatment notes** export by type and creation time.
   Use `browser_download` on its ready link, then `read_csv` with successive
   `next_offset` values until null. Read every row.

Map the actual CSV headers (never assumed column positions):

- **Treatment Note ID** → `sourceId`
- **Patient ID** → `note.clientId` (Cliniko ID, not Carepatron ID)
- **Appointment ID** → `note.appointmentId` if present; otherwise null
- **Practitioner** → `sourceRefs.authorName`; the export has no practitioner ID,
  so `note.authorId=null` unless an ID is separately verified
- **Template ID** → `sourceRefs.templateId`, NOT `note.template` (which is descriptive text)
- **Title** → `note.title`
- **Draft = Yes** → `note.status="draft"`; otherwise unknown unless signing is evidenced
- **CreatedAt** → `note.createdAt` (ISO 8601 with seconds and original UTC offset)
- **Text** → `note.content` (copy the complete CSV field directly).

Do not rewrite, summarize, split question sections, normalize HTML,
trim whitespace or change line breaks in the **Text** field.

This CSV has no service date, signature timestamp or Carepatron note type.
Use `dateOfService=null`, `signedAt=null`, and `type=null` when unknown.
Do NOT substitute `CreatedAt` for `dateOfService`, infer `intake` from
"Initial Consultation", or infer a signature from **UpdatedAt**.
Set `template=null` without a verified descriptive template name.
**UpdatedAt** has no destination field in this schema.

Preserve source IDs as strings, including leading zeros. For spreadsheet
values such as `="00123"`, retain `00123` without evaluating formulas.
Do not match patients by name or invent appointment or author IDs.
Report omissions, unknown required fields and incomplete coverage in
`limitations`. Do not edit source records or open unrelated pages.
