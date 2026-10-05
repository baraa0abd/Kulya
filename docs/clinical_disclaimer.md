# Clinical disclaimer

Kulya is a documentation and review-support demo. It is **not a medical device** and does not make
clinical decisions.

- **Thresholds.** All thresholds are configurable placeholders for the demo and must be reviewed by
  the clinical team before any real use. They are not clinical guidance. They live in
  `backend/rules/config.yaml`; every flag records the hash of the configuration that produced it.
- **Flags** are produced by deterministic code from typed vitals and nurse-approved facts. A flag
  states what was recorded (values, sessions, notes). It never says what the finding means or what
  to do about it.
- **AI output** is always a draft. A nurse approves extractions; a doctor approves summaries. The
  AI never enters or changes numeric vitals, never decides what is abnormal, and never suggests a
  diagnosis, medication, or treatment change.
- **Field ranges** on the session form (for example systolic 50–260 mmHg) only catch typing
  mistakes. They are not clinical limits.
- **Data.** Every patient, session, and note in this repository is synthetic. No real patient
  information is used, and the application refuses to start in demo mode otherwise.
