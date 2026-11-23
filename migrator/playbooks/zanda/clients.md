# Zanda client profiles — sequential in-app extraction

Do not use Tools → Data Export, CSV, reports, bulk export, or patient exports.
Read individual records in the authenticated UI. Start with `browser_observe`.
Use `save_result=false` unless an observation must be retrieved later.

## Enumerate clients

1. Navigate to **People → Search**. Inspect the search/list filters and select
   only profile type **Client** (or the exact patient/client type shown).
   Do not treat contacts, referrers, third parties, or shared profiles as
   patients merely because they appear in People.
2. Record the complete ordered list of visible client names and stable client
   identifiers. Visit every page of the result list and use pagination until
   the end. Do not rely on a partial search result or a currently loaded page.
3. For each client, one at a time, open the profile and select **Details**.
   Finish that profile's detail extraction before opening the next client.
   Re-observe after each navigation and use only fresh refs.

## Destination mapping

Output one item per client in `records` as
`{ "sourceId": "<verified Zanda ID>", "client": { ... } }`. Use the stable
profile ID from a labelled field or verified profile URL. If only a Client
Number is shown, preserve it exactly as a string, including leading zeros, and
verify it uniquely identifies the client. Never fabricate or normalize IDs.

Map the profile's exact details to Carepatron client keys:

- Legal first/last name → `firstName`, `lastName` (both required)
- Preferred name → `preferredName`
- Date of birth → `dateOfBirth` as `YYYY-MM-DD`
- Recorded sex → `sex` only when `female` or `male`; other values → null
- Gender identity and pronouns → `genderIdentity`, `pronouns`
- Email and phone/mobile → `email`, `phone`
- Address → `address.line1`, `line2`, `city`, `state`, `postalCode`, `country`
- Client status → `status` only when the source status maps unambiguously to
  `active`, `inactive`, or `discharged`; do not reinterpret custom labels
- Explicit referral/how-heard source → `referralSource`
- Explicit account-created timestamp with offset → `createdAt`
- Source-recorded diagnoses → `diagnoses: [{"code":"...","description":"..."}]`
- Client-linked contacts → `contacts: [{"name":"...","relationship":"...",
  "phone":null,"email":null,"isEmergencyContact":null,"isGuardian":null}]`
- Explicit billing designation → `billingType` only when it clearly means
  `insurance` or `self_pay`

For addresses, include an object only if all required address components are
present. Use an explicit two-letter country code; do not infer country from a
practice location, city, or phone prefix. Do not invent diagnosis codes,
contact details, referral sources, billing types, or dates. Include emergency
and guardian flags only when the profile explicitly marks them; otherwise use null
for the unknown flags. Keep each contact's actual relationship.

## Practitioner relationship and data scope

The destination `primaryClinicianId` expects a Carepatron ID. Do not put a
Zanda user/practitioner ID or name there. The current clients stage has no
`sourceRefs` property for the source primary-practitioner association; use null for
`primaryClinicianId` and record the source practitioner name/ID in
`limitations` until the stage output model is extended to preserve it.

Diagnoses must have the source code and description. Do not convert another
diagnosis code system to ICD-10-CM. Report codes that cannot be represented
faithfully. For contact records, do not open unrelated profiles to fill in
missing fields.

Do not extract appointments or notes in this stage; their dedicated playbooks
perform sequential profile-by-profile passes. Do not include source `id` inside
the Carepatron `client` object. Do not invent destination IDs.

## Save each record

After completing each individual record, call `append_record` once with that
record as a JSON object encoded in the `record` string. Use the exact `records`
item shape described above, including destination field names and source IDs.
Before the final response call `load_records` with `stage="current"`, then return the entire loaded
list as `records` with your `limitations`. Report incomplete or omitted records;
do not invent values to fill required fields.

## Completion

Continue through every client and every list page. Omit any record lacking a
verified source ID or either required name, and explain the omission. Return
`records` and `limitations`; do not claim completeness if the list, a profile,
or its Details page was inaccessible or the run ended before the final client.
