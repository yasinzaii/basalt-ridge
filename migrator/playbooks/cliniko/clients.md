
# Cliniko patient CSV export

Use the signed-in fictional trial account. Start with `browser_observe`.
Use `save_result=false` unless an observation needs to be retrieved later.

1. Navigate to **Settings → Data exports**.

2. Under **Data to export**, select **Patients**.
   Keep **File format** as **Spreadsheet (.csv)**.

3. Under **Date range**, clear both dates:
   - Click the **From** textbox itself to open its calendar.
   - In the snapshot returned by that click, find its enabled **Any time** button
     and click its current ref. Do not click a disabled calendar button.
   - Click the **To** textbox itself, then use its returned snapshot to click
     that calendar's enabled **Any time** button.
   - Verify both date fields are cleared. If blocked, report the limitation;
     do not repeat the same failed click without a relevant state change.

4. Enable **Include archived records** if the active UI supports it. A warning
   marked `[aria-hidden]` alone does not establish that it is unsupported.
   If a visible warning says archived records are unsupported, skip the option
   and report it. A checked box alone does not prove coverage; report uncertainty
   if the export does not establish whether archived patients are included.

5. Note the existing exports, then click **Export data** once.

6. Call `browser_wait` with `seconds=5`, then inspect the returned snapshot
   for the new **Patients** export. If it is still pending, wait another
   five seconds and check again. Match the export by type and creation time;
   download only once it is ready. Never submit again while it is pending.

7. Download the new export using `browser_download`.

8. Read the downloaded CSV using `read_csv`, following
   `next_offset` until null. Map the CSV columns to the
   Carepatron client schema.

Preserve patient IDs as `sourceId` strings. For IDs such as
`="00123"`, preserve `00123` without evaluating formulas.

Do not invent missing fields, relationships, billing types,
or destination IDs. Report unavailable fields and incomplete
exports in `limitations`.

Do not modify patient records or open unrelated pages.
