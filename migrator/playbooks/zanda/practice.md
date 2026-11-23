# Zanda practice setup

Read the signed-in account's settings only. Do not save, edit, activate,
deactivate, or create anything. Start with `browser_observe`; use current
snapshot refs only. Use `save_result=false` unless a result must be retrieved.

## 1. Business identity

Navigate to **Settings → Practice → Business Info**. Read the business name,
country, business address, email, phone/fax, Tax ID/ABN, organization NPI,
taxonomy code, time zone, locale, and any explicitly displayed currency.
Zanda has one account-wide business identity. Do not combine accounts or
mistake location addresses for the account-level address.

Map to `practice`:

- Business Name → `name`
- Legal/registered business name → `legalName` only if separately shown
- Organization NPI → `npi` only if explicitly labelled as an organization NPI
- Tax ID/ABN → `taxId` only when it is the destination's supported tax ID
- Organization taxonomy → `taxonomyCode`
- Business email/phone/website → `email`, `phone`, `website`
- Complete business address → `address.line1`, `line2`, `city`, `state`,
  `postalCode`, `country`
- IANA account time zone → `timezone`
- Exact ISO currency code → `currency`

Do not infer a currency code from a currency symbol, country, or locale. If the
UI does not establish the exact code, leave `currency` unset and report it.
For an incomplete address, leave `address` null and report the missing parts.
Use an explicit two-letter country code; do not infer country from a city.

## 2. Locations

Navigate to **Settings → Practice → Locations** and inspect every listed
location. Open each location's read-only details. Capture its stable source ID
from a labelled ID or verified detail URL; preserve the URL in
`sourceRefs.url`. Never invent an ID from its name.

Map each item to `{ "sourceId": ..., "location": ..., "sourceRefs": {"url": ...} }`:

- Location name → `location.name`
- Explicit in-person type → `location.kind="in_person"`
- Explicit telehealth video type → `location.kind="telehealth"`
- Address components → `location.address.line1`, `line2`, `city`, `state`,
  `postalCode`, `country`
- Location phone → `location.phone`
- CMS place-of-service code and description →
  `location.placeOfService.code` and `.description`, only when explicitly
  recorded

The destination `kind` enum has only `in_person` and `telehealth`. Do not map a
Phone location to either value without a confirmed semantic match. Do not infer
CMS codes from the setting name or address. Include inactive locations when
they are listed; preserve their inactive state in `limitations` because the
destination location schema has no status field.

## 3. Users and practitioners

Navigate to **Settings → Team → Users → User Management**. Inspect every user,
including inactive/deactivated users where available. Then navigate to
**Settings → Team → Practitioners** and inspect every practitioner profile.
Keep user and practitioner IDs distinct. For each user, use the source user ID
as `sourceId`, the linked practitioner ID as `sourceRefs.practitionerId`, and
the verified detail URL as `sourceRefs.url`.

Map the user/practitioner record to `teamMember`:

- User's first/last name and email → `firstName`, `lastName`, `email`
- Explicitly identified account owner → `role="owner"`
- Explicit practitioner association/role → `role="clinician"`
- Explicit practice-manager title/role → `role="practice_manager"`
- Practitioner job title → `title`
- Explicit post-nominal qualifications → `credentials`
- Individual NPI → `npi` only when explicitly recorded and valid as a 10-digit
  US NPI
- Explicit licence details → `license.type`, `license.number`, `license.state`,
  `license.expiresOn`
- User status → `status="active"` or `"deactivated"` only when that state is
  directly shown

Do not infer a person's credentials from Provider Type, Job Title, or user
permissions. Do not fabricate NPI, US licences, state codes, or expiration
dates. A practitioner profile without an associated user is not automatically
a login/team user; report it if the current team schema cannot represent it.
Omit a team record without its required name/email and report the omission.

## 4. Services

Navigate to **Settings → Billing → Services**. Inspect all active and inactive
service templates and their detail pages. Capture each verified service ID and
URL. Map to `{ "sourceId": ..., "service": ..., "sourceRefs": {"url": ...} }`:

- Service name → `service.name`
- CPT/HCPCS code → `service.cptCode` only if explicitly identified as CPT or
  HCPCS; a generic Item Number/Code is not automatically a billing code
- Explicit billing modifiers → `service.modifiers`
- Service-specific configured duration → `service.durationMinutes`
- Explicit current service fee → `service.rate`, in the practice currency

Do not use a single appointment's elapsed time as a configured service
duration. If the UI does not show a service-specific duration, omit that
service because `durationMinutes` is required and report the gap. A zero fee is
valid only if the UI explicitly shows zero.

## 5. Payers

Navigate to **Settings → Payments → Insurers**. Read every practice-level
insurer/payer entry and its displayed type. Map to
`{ "sourceId": ..., "payer": ..., "sourceRefs": {"url": ...} }`:

- Insurer name → `payer.name`
- Electronic clearinghouse payer ID → `payer.electronicPayerId` only if that
  exact identifier is shown
- Explicit commercial/private insurer → `payer.type="commercial"`
- Explicit Medicare → `payer.type="medicare"`
- Explicit Medicaid → `payer.type="medicaid"`
- Other explicitly identified scheme → `payer.type="other"`

Do not map a practitioner provider number, client member number, or generic
insurer type to `electronicPayerId`. Do not classify a scheme as Medicaid by
similarity. If no explicit practice-level list is available, return an empty
`payers` array and report the limitation.

## Save each record

After completing the practice details or each individual team member, location,
service, or payer, call `append_record` once. Encode a JSON object in the
`record` string as `{"kind":"practice","record":{...}}` for practice details,
or use `kind` of `team`, `locations`, `services`, or `payers` with `record` set
to that collection's complete wrapper described above. Use the destination
fields and source IDs required by the final schema.

Before the final response call `load_records` with `stage="current"`. Use the saved practice record for
`practice`, and group the other saved records into their matching arrays. Return
these with `limitations`; do not include the `kind`/`record` envelope in the
final output. Report incomplete or omitted records; do not invent values.

## Completion

Return the exact practice-stage object: `practice`, `team`, `locations`,
`services`, `payers`, and `limitations`. Use null for unknown nullable fields,
empty arrays only when the relevant list was actually inspected and is empty.
Never put source IDs into Carepatron destination ID fields. Report inaccessible
pages, unmapped source fields, incomplete coverage, and ambiguous identity in
`limitations`. Stop after these settings sections; do not open client records.
