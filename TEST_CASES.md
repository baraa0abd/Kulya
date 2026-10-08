# Screen and input test cases

Tests use synthetic demo data and the offline mock AI provider. Input coverage uses equivalence
classes and boundary values; exhaustive testing of arbitrary strings and numbers is not finite.

## Screen inventory

| Screen / route | Roles exercised | Expected behavior | Automated cases |
|---|---|---|---|
| `/` | Patient | Redirect to the user's dashboard | Screen sweep |
| `/login/` | Anonymous, all demo clinical roles | Required credentials; failed login stays on the page; valid login opens role dashboard | Empty input, unknown account (including screenshot example LJLK), recovery, Arabic/English, mobile |
| `/doctor/` | Doctor | Assigned patients and review queue only | Screen sweep, workflow, care-team isolation |
| `/nurse/` | Nurse | Schedule, assigned patients, feedback and notifications | Screen sweep, scheduling and workflow |
| `/dietitian/` | Dietitian | Assigned nutrition patients and pending work | Screen sweep and nutrition workflow; session survives reload |
| `/patient/` | Patient, allowed/expired family | Released summaries, appointments and appropriate consent controls | Screen sweep, workflow, home measurements, consent API tests |
| `/nurse/sessions/[id]/` | Nurse | Start, record care, complete; errors do not save invalid data | Weight boundaries; blank vital, machine, note, action, event; full clinical workflow |
| `/doctor/sessions/[id]/` | Doctor | Review AI output, feedback, verify and release | Full workflow; unauthorized access API tests |
| `/doctor/patients/[id]/` | Doctor | History, labs and versioned prescriptions | Screen sweep; empty/non-numeric/fractional/out-of-range duration; backend versioning |
| `/patient/nutrition/` | Patient, allowed/expired family | Approved plan and diary totals, or consent empty state | Screen sweep, retry after 503, nutrition workflow |
| `/patient/nutrition/add/` | Patient, allowed/expired family | Propose foods without saving, confirm/edit, save meal | Recognition workflow; empty/zero/negative/text amounts; Unicode/HTML as inert text |
| `/patient/nutrition/history/` | Patient, allowed/expired family | Diary, unknown nutrients and permitted removal | Screen sweep, saved meal; backend correction/removal tests |
| `/patient/nutrition/suggestions/` | Patient, allowed/expired family | Approved personalized ideas; no approval controls | Screen sweep, nutrition workflow, backend approval filtering |
| `/patient/nutrition/labs/` | Patient, allowed/expired family | Only authorized/released lab information | Screen sweep, nutrition workflow, backend release/consent tests |
| `/patient/nutrition/reports/` | Patient, allowed/expired family | Released reports and print control | Screen sweep, clinician-to-patient release workflow |
| `/doctor/patients/[id]/nutrition/` | Doctor, dietitian, nurse | Clinicians approve plans/ideas; nurses read and observe | Screen sweep, plan limits 0/100001/text, nutrition workflow |
| `/doctor/patients/[id]/nutrition/lab-review/` | Doctor, dietitian, nurse | Facts and clearly marked AI drafts with role controls | Screen sweep, workflow, backend approve/reject and failure tests |
| `/doctor/patients/[id]/nutrition/reports/` | Doctor, dietitian, nurse | Clinicians draft/release reports; patient sees only releases | Screen sweep, nutrition workflow, backend release authorization |

The sweep visits each permitted route, checks loading finishes, checks application alerts and
uncaught browser exceptions, reloads the session, signs out and verifies protected access redirects.
A patient is separately tested against all staff routes, including dynamic routes with arbitrary IDs.

## Input partitions and outcomes

| Input class | Examples | Expected outcome |
|---|---|---|
| Missing required text | Empty, spaces, newline | Validation error; no submission |
| Credentials | Empty username/password, unknown account, valid account, spaced/Unicode password | Reject invalid credentials; preserve password exactly; recover on next valid login |
| Missing numeric measurement | Empty, spaces, tab, null, undefined, booleans | Reject; do not coerce missing input to zero |
| Invalid numeric measurement | `abc`, `NaN`, infinities | Reject; no persisted vital |
| Actual numeric data | Zero, negative, decimal, padded number | Parse as numbers; apply kind-specific server constraints |
| Vital ranges | SBP 40–300, DBP 20–200, HR 20–250, temperature 30–45, SpO2 50–100, weight 20–300 | Inclusive endpoints save with correct unit; one below/above rejects without saving |
| Session weights | 20, 300, 19, 301, missing | Endpoints accepted; outside rejected; optional missing stays absent |
| Session UF | 0, 10000, -1, 10001, fractional, text, null | Inclusive integer endpoints accepted; invalid input rejected |
| Prescription duration | Empty, 29, 601, 30.5, text | Validation error |
| Nutrition limit | 0, 100001, text | Validation error |
| Meal quantities | Empty, 0, -1, text, 1 | Invalid amounts rejected; valid manual unmatched food saves as needs review |
| User-entered content | Arabic and `<script>` text | Stored/displayed as text, without script execution |
| Server failures | 400, 403, 404, 409, 429, 500, 503; non-JSON 502 | Structured API errors; transient screen error can be retried |
| Expired authentication | Access token expired; refresh valid/invalid | One refresh and replay; clear session on failed refresh; no loop |
| Empty delete response | 204 | Successful completion without JSON parsing error |

## Running

```powershell
cd backend
.venv/Scripts/python -m pytest
# In a separate terminal, use a higher rate limit only for local synthetic testing:
$env:THROTTLE_LOGIN='1000/min'
.venv/Scripts/python manage.py runserver 127.0.0.1:8001 --noreload

# In a frontend terminal:
cd frontend
$env:BACKEND_URL='http://127.0.0.1:8001'
$env:E2E_DIST_DIR='.next-e2e'
npm run dev -- --hostname 127.0.0.1 --port 3001

# In another frontend terminal:
npm test
npm run typecheck
npm run lint
$env:E2E_BASE_URL='http://127.0.0.1:3001'
npx playwright test
```

Browser tests add synthetic measurements, meals, sessions, a plan version, clinician feedback
and report releases to the demo database. They must not run against real patient data. API tests
use Django's separate test database. Browser traces are retained locally on failures.

## Limits requiring separate validation

Physical camera capture, microphone permission/audio recognition, real external AI/USDA services,
production hosting, non-Chromium browsers, and a clinical assessment are not verified by these
automated suites. Photo/voice input and clinical correctness require separate acceptance checks.
The mobile check exercises Arabic login at 390 × 844; it is not a visual audit of every mobile screen.
