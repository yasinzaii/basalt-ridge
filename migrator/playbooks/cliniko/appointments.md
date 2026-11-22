# Cliniko appointment CSV export

Use the signed-in fictional trial account. Start with `browser_observe`.
Use `save_result=false` unless an observation needs to be retrieved later.

1. Navigate to **Settings → Data exports**.

2. Select **appointments (deprecated)** under **Data to export**.
   Keep **Spreadsheet (.csv)**. If unavailable or disabled, report the blocker;
   do not substitute another export type.

3. Clear the date range:
   - Click the **From** textbox to open its calendar.
   - In the returned snapshot, click that calendar's enabled **Any time** button.
   - Repeat for **To**.
   - Verify both dates are cleared.

4. Enable **Include archived records** if supported.
   Report uncertain archived coverage.

5. Note existing exports and click **Export data** once.
   Call `browser_wait(seconds=5)`. If still pending, wait again.
   Never submit the same export twice.

6. Identify the newly generated export by type and creation time.
   Download it using `browser_download`, then read every CSV batch
   using `read_csv` and `next_offset` until null.

7. Map verified CSV fields to the Carepatron appointment schema:

   - Appointment ID → `sourceId`
   - Patient IDs → `appointment.clientIds`
   - Practitioner ID → `appointment.clinicianId`
   - Practitioner → `sourceRefs.clinicianName`
   - Appointment Type → `sourceRefs.serviceName`
   - Business → `sourceRefs.locationName`
   - Recurring series ID, if available → `appointment.seriesId`
   - Appointment Type → `appointment.title`, if appropriate
   - Start Time → `appointment.startsAt`
   - End Time → `appointment.endsAt`
   - Appointment Notes → `appointment.memo`

8. Map appointment status only from verified evidence:
   - Explicit whole-appointment cancellation → `cancelled`
   - Explicit whole-appointment no-show → `no_show`
   - Patient Arrived alone does not establish `completed`.
   - Otherwise use null and report the unknown status.
   - Do not infer status from appointment dates or reminder flags.

Use exact CSV headers, not assumed column positions.
Preserve source IDs as strings. For values such as `="00123"`,
preserve `00123` without evaluating formulas.

Convert timestamps to ISO 8601 with seconds and a timezone:
`2026-11-23 09:00:00 +1300` → `2026-11-23T09:00:00+13:00`.
Do not use Created At as the appointment start time.

For group appointments, preserve all verified patient IDs.
Do not infer membership by patient name or treat a participant's
cancellation as cancellation of the whole appointment.

These are staged extraction records, not API payloads. `appointment.clientIds`
must contain a nonempty array of verified source patient IDs; omit a record with
no patient IDs and report it. Preserve an available source Practitioner ID in
`appointment.clinicianId`; use null and report it only when the ID is missing.
Never substitute a practitioner name for an ID.

`sourceRefs` contains only clinician, service and location name hints.
The export provides service/location names, so use null for `appointment.serviceId`
and `appointment.locationId`; do not invent IDs from those names.
Preserve an explicitly provided recurring series ID in `appointment.seriesId`,
otherwise use null. A later importer must resolve source references before sending
records to Carepatron.

Report missing fields, ambiguous mappings, omitted records
and incomplete coverage in `limitations`.

Do not modify source records or open unrelated pages.
