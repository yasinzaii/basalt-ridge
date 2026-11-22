
# Cliniko appointment CSV export

Use the signed-in fictional trial account. Start with `browser_observe`.
Use `save_result=false` unless an observation needs to be retrieved later.

1. Navigate to **Settings → Data exports**.

2. Select **appointments (deprecated)** under **Data to export**.
   Keep **Spreadsheet (.csv)**. If unavailable, report the blocker.

3. Clear the date range:
   - Click the **From** textbox to open its calendar.
   - Click the enabled **Any time** button.
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
   - Patient IDs → `sourceRefs.clientIds`
   - Practitioner ID → `sourceRefs.clinicianId`
   - Practitioner → `sourceRefs.clinicianName`
   - Appointment Type → `sourceRefs.serviceName`
   - Business → `sourceRefs.locationName`
   - Recurring series ID, if available → `sourceRefs.seriesId`
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

The `appointment` object must contain only Carepatron fields.
Set unresolved `appointment.clientIds`, `clinicianId`,
`serviceId`, and `locationId` to null. Keep original source
references separately in `sourceRefs`; never copy source IDs
into destination ID fields.

Preserve the Practitioner ID from the CSV as
`appointment.clinicianId`. Never replace an available
source ID with null or a practitioner name.
If no practitioner ID exists, use null and report it.

Report missing fields, ambiguous mappings, omitted records
and incomplete coverage in `limitations`.

Do not modify source records or open unrelated pages.
