# Using the nutrition screens

## Patient

1. Open **Nutrition → Add a meal**. Food and portion controls are visible immediately.
2. Search in Arabic or English and choose a food, or add an unlisted food.
3. Enter the amount and unit. Arabic digits and decimal separators are accepted. The selected
   catalog food controls its displayed name and nutrient calculation.
4. Confirm each food and portion, choose the meal and time, and save. Future times, invalid
   quantities, unsupported portions and unconfirmed rows are blocked with an explanation.
5. Open **Meal diary** to filter dates or confirmation status. **Correct meal** opens the saved
   foods and quantities; changing a quantity requires confirmation again. Saving recalculates
   nutrients on the server. Removing a meal withdraws it and retains the audit history.

Nutrition estimates in the diary are collapsed until opened. Weekly averages show the number
of days with complete data for each nutrient. Missing values mean incomplete data, not zero.
An unlisted food may be saved as a checked personal record, but its nutrient estimate stays
unknown and the meal stays marked for review.

The optional assistant proposes foods without saving them. Offline demo text recognition
understands numeric Arabic portions such as `٢ حبة بيض، ١٫٥ كوب رز`. Photo recognition is shown
only when the real provider is configured; offline mode states its limitation. Speech failures
offer direct entry instead. All proposed foods still require confirmation.

## Nurse

Open **Nutrition** beside a patient on the assigned-patient list. Review their diary and approved
plan, then record eating difficulties, nausea or appetite concerns. Refer an observation to the
doctor and dietitian when appropriate. Nurses cannot approve plans or release reports.

## Doctor or dietitian

Review the diary, food/lab view and nursing observations. The plan form starts with the active
plan's values, so updating guidance does not silently erase its limits or allergies. Approval
creates a new version. Arabic names for the catalog's fish, milk, egg and gluten allergens
are normalized before recipe exclusion. Review AI drafts and explicitly release reports before
patients see them.

## Demo data and browser tests

Bundled food values remain approximate, unverified demonstration data. No new medical limits
are invented. Unknown foods retain unknown values; the app does not fabricate precise results.

Browser tests should use a separate database, rather than write into the interactive demo:

```powershell
# Terminal 1, in backend: creates/reuses the local database suffixed _e2e,
# migrates and seeds it, runs mock AI eagerly, and serves on port 8001.
./.venv/Scripts/python.exe manage.py run_e2e_server

# Terminal 2, in frontend:
$env:BACKEND_URL='http://127.0.0.1:8001'
$env:E2E_DIST_DIR='.next-e2e'
npm run dev -- --hostname 127.0.0.1 --port 3001

# Terminal 3, in frontend:
$env:E2E_BASE_URL='http://127.0.0.1:3001'
npm run e2e
```

The setup is restricted to DEBUG and a local PostgreSQL server. It never drops a database and
does not modify the interactive database. Repeated runs reuse test records. The direct-entry
and correction test withdraws its own meal afterward.
