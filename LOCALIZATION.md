# Arabic interface coverage

Arabic is the default locale, with right-to-left layout. English remains available through
the **الإنجليزية** button; **العربية** switches back. The preference also updates the document
language, direction, title and description.

The translation registry covers interface labels, navigation, statuses, form validation,
API error messages, units, laboratory analytes, chart accessibility labels and tooltips,
food and recipe names, preparation steps, protocol headings, synthetic names, and the
deterministic demo clinical and nutrition narratives. Template translations retain original
numeric values. API payloads, identifiers, select values and stored records are not changed.

`frontend/tests/localization.test.ts` audits declared display copy throughout the application
and requires Arabic counterparts without remaining Latin words. It also compares translations
against the bundled food and recipe catalogue and tests generated error/narrative templates.
Add new interface copy through `tr`, `Tx`, or the shared translated component props, then
add its Arabic counterpart to the registry. New generated messages need template coverage.

`frontend/e2e/localization.spec.ts` checks the permitted screens for doctor, nurse, patient,
dietitian and family roles. It verifies Arabic controls, RTL layout, localized invalid-login
errors, and switching both ways between Arabic and English.

Free-form user records, unfamiliar personal names, technical identifiers and external provider
content have no automatic machine translation: their original text is preserved. The tests
verify the bundled demo content and interface, not arbitrary future third-party prose.

Run from `frontend`:

```powershell
npm test
npm run typecheck
npm run lint
$env:E2E_BASE_URL='http://127.0.0.1:3001'
npx playwright test e2e/localization.spec.ts
```

Browser checks require a seeded local stack. A separate test API/frontend is recommended
for the full suite so repeated sign-ins do not hit the normal login rate limit.
