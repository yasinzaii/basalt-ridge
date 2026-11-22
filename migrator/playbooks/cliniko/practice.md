# Cliniko practice setup

Use the signed-in account and these settings pages only. Never open patient records.

1. **Settings → Business information**
   Treat each business as a separate location. Keep active businesses distinct; Ignore archived businesses, never unarchive to inspect them. Read the business/display name, registration name/number, address, website, email reply-to, contact details, and additional communication/invoice information. Report ambiguity about the practice-wide identity. Handle time zones as described in step 4.

2. **Settings → Users & practitioners**
   Include every listed user. Enable “Show inactive users” if available; otherwise report that inactive-user coverage is unverified. Read name, email, security role and practitioner status. In practitioner settings, read Designation, Description and Reference numbers, preserving each number’s type and associated business. Blank fields and empty reference rows are unset; do not reclassify identifiers as NPI or US licences without explicit evidence.

3. **Settings → Appointment types; Settings → Billable items**
   Read every appointment type’s name and duration. For billable items, read name, code, type, price and tax setting; note blank codes. Link codes and fees to appointment types only through their explicit “Related billable items” association, never similar names. Report unclear associations as unconfirmed.

4. **Settings → General settings**
   Read invoice currency, account country, account time zone and whether advanced support for multiple time zones is enabled. Use displayed business-specific time zones from Business information where applicable; otherwise report the account time zone as the default. Do not infer currency or time zone from an address. Read other settings only if specifically requested.

5. **Insurance payers**
   Use only an explicit practice-level payer list visible within these settings, not general contacts. If none is available, return an empty list and report coverage as unavailable.

Stop after these steps. Use source-only details as context or limitations, not extra fields in the Carepatron JSON.


Preserve source identities while reading these pages:
- Team: user ID as `sourceId`; explicitly associated practitioner ID as
  `sourceRefs.practitionerId`. A user ID is not automatically a practitioner ID.
- Locations: business ID as `sourceId`. Services: appointment type ID as
  `sourceId`, not the related billable item ID. Payers: the payer's own ID if shown.
- Read IDs from verified detail links/URLs or labelled fields and retain the
  detail URL as `sourceRefs.url`. If unavailable, use null and report the gap.
  Never infer an ID from a name or fabricate one. Names/emails remain in the
  resource fields as later lookup evidence.
