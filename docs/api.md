# Kulya API

Generated from the OpenAPI schema by `backend/gen_api_md.py` — do not edit by hand.
Live schema: `GET /api/schema/`, Swagger UI: `GET /api/docs/`.

Errors always use: `{"error": {"code", "message_ar", "message_en", "details"}}`.

| Method | Path | Request body | Response | Notes |
|---|---|---|---|---|
| GET | `/api/v1/audit/` | — | `PaginatedAuditLogList` | Who did what, newest first. Read-only; there is no endpoint that edits the audit log. `?object_id=`, `?object_type=`, `?page=` |
| POST | `/api/v1/auth/token` | `KulyaTokenObtainPair` | `KulyaTokenObtainPair` | Takes a set of user credentials and returns an access and refresh JSON web token pair to prove the authentication of those credentials. |
| POST | `/api/v1/auth/token/refresh` | `TokenRefresh` | `TokenRefresh` | Takes a refresh type JSON web token and returns an access type JSON web token if the refresh token is valid. |
| GET | `/api/v1/extraction-drafts/` | — | `PaginatedExtractionDraftList` | `?page=`, `?status=` |
| GET | `/api/v1/extraction-drafts/{id}/` | — | `ExtractionDraft` |  |
| POST | `/api/v1/extraction-drafts/{id}/approve/` | `ApproveDraft` | `ExtractionDraft` |  |
| POST | `/api/v1/extraction-drafts/{id}/reject/` | `Reject` | `ExtractionDraft` |  |
| POST | `/api/v1/extraction-drafts/{id}/retry/` | — | `ExtractionDraft` |  |
| GET | `/api/v1/me/summaries/` | — | `PaginatedSummaryList` | `?page=` |
| GET | `/api/v1/notes/{id}/` | — | `Note` |  |
| GET | `/api/v1/patients/` | — | `PaginatedPatientList` | `?page=` |
| GET | `/api/v1/patients/{id}/` | — | `Patient` |  |
| GET | `/api/v1/patients/{id}/flags/` | — | `PaginatedFlagList` | `?page=` |
| POST | `/api/v1/patients/{id}/sessions/` | `Session` | `Session` |  |
| POST | `/api/v1/patients/{id}/summaries/` | `SummaryRequest` | `Summary` |  |
| GET | `/api/v1/patients/{id}/timeline/` | — | `PaginatedTimelineSessionList` | Sessions newest first, each with vitals, notes, approved facts, and its flags. 20 per page. `?page=` |
| GET | `/api/v1/sessions/{id}/` | — | `Session` |  |
| POST | `/api/v1/sessions/{id}/notes/` | `Note` | `NoteCreated` |  |
| GET | `/api/v1/summaries/{id}/` | — | `Summary` |  |
| POST | `/api/v1/summaries/{id}/approve/` | — | `Summary` |  |
| POST | `/api/v1/summaries/{id}/reject/` | `Reject` | `Summary` |  |

## Schemas

### AccessTypeEnum
- one of: `AVF` | `AVG` | `CVC`

### ApproveDraft
- `edited_payload`: any

### AudienceEnum
- one of: `clinician` | `patient`

### AuditLog
- `id`: integer (read-only)
- `actor`: integer (read-only)
- `action`: string (read-only)
- `object_type`: string (read-only)
- `object_id`: integer (read-only)
- `before`: any (read-only)
- `after`: any (read-only)
- `created_at`: string (read-only)

### ExtractionDraft
- `id`: integer (read-only)
- `note`: integer (read-only)
- `note_text_ar`: string (read-only)
- `session`: integer (read-only)
- `payload`: any (read-only)
- `edited_payload`: any (read-only)
- `status`: any (read-only)
- `validation_errors`: any (read-only)
- `model_name`: string (read-only)
- `prompt_version`: string (read-only)
- `created_at`: string (read-only)
- `reviewed_by`: integer (read-only)
- `reviewed_at`: string (read-only)

### ExtractionDraftStatusEnum
- one of: `pending` | `approved` | `rejected` | `invalid`

### Flag
- `id`: integer (read-only)
- `patient`: integer (read-only)
- `session`: integer (read-only)
- `rule_id`: string (read-only)
- `severity`: any (read-only)
- `message_ar`: string (read-only)
- `evidence`: any (read-only)
- `created_at`: string (read-only)
- `rules_version`: string (read-only)

### KulyaTokenObtainPair
- `username`: string
- `password`: string

### Note
- `id`: integer (read-only)
- `session`: integer (read-only)
- `author`: integer (read-only)
- `text_ar`: string
- `created_at`: string (read-only)
- `supersedes`: integer

### NoteCreated
- `id`: integer (read-only)
- `session`: integer (read-only)
- `author`: integer (read-only)
- `text_ar`: string
- `created_at`: string (read-only)
- `supersedes`: integer
- `draft_id`: integer (read-only)
- `draft_status`: string (read-only)

### PaginatedAuditLogList
- `count`: integer
- `next`: string
- `previous`: string
- `results`: array

### PaginatedExtractionDraftList
- `count`: integer
- `next`: string
- `previous`: string
- `results`: array

### PaginatedFlagList
- `count`: integer
- `next`: string
- `previous`: string
- `results`: array

### PaginatedPatientList
- `count`: integer
- `next`: string
- `previous`: string
- `results`: array

### PaginatedSummaryList
- `count`: integer
- `next`: string
- `previous`: string
- `results`: array

### PaginatedTimelineSessionList
- `count`: integer
- `next`: string
- `previous`: string
- `results`: array

### Patient
- `id`: integer (read-only)
- `code`: string (read-only)
- `display_name_ar`: string (read-only)
- `birth_year`: integer (read-only)
- `is_synthetic`: boolean (read-only)
- `created_at`: string (read-only)
- `attention_flag_count`: integer (read-only)

### Reject
- `reason`: string

### Session
- `id`: integer (read-only)
- `patient`: integer (read-only)
- `session_date`: string
- `start_time`: string
- `end_time`: string
- `pre_sbp`: integer
- `pre_dbp`: integer
- `post_sbp`: integer
- `post_dbp`: integer
- `min_intra_sbp`: integer
- `pre_weight_kg`: string
- `post_weight_kg`: string
- `uf_volume_ml`: integer
- `access_type`: AccessTypeEnum
- `created_by`: integer (read-only)
- `created_at`: string (read-only)

### SessionFacts
- `symptoms`: any (read-only)
- `access_findings`: any (read-only)
- `staff_actions`: any (read-only)
- `updated_at`: string (read-only)

### SeverityEnum
- one of: `info` | `attention`

### Summary
- `id`: integer (read-only)
- `patient`: integer (read-only)
- `audience`: any (read-only)
- `period_start`: string (read-only)
- `period_end`: string (read-only)
- `sentences`: array (read-only)
- `status`: any (read-only)
- `validation_errors`: any (read-only)
- `model_name`: string (read-only)
- `prompt_version`: string (read-only)
- `created_at`: string (read-only)
- `approved_by`: integer (read-only)
- `approved_at`: string (read-only)

### SummaryRequest
- `audience`: AudienceEnum
- `period_start`: string
- `period_end`: string

### SummarySentence
- `text_ar`: string
- `citations`: array

### SummaryStatusEnum
- one of: `draft` | `approved` | `rejected` | `invalid`

### TimelineSession
- `id`: integer (read-only)
- `patient`: integer (read-only)
- `session_date`: string
- `start_time`: string
- `end_time`: string
- `pre_sbp`: integer
- `pre_dbp`: integer
- `post_sbp`: integer
- `post_dbp`: integer
- `min_intra_sbp`: integer
- `pre_weight_kg`: string
- `post_weight_kg`: string
- `uf_volume_ml`: integer
- `access_type`: AccessTypeEnum
- `created_by`: integer (read-only)
- `created_at`: string (read-only)
- `notes`: array (read-only)
- `facts`: any (read-only)
- `flags`: array (read-only)

### TokenRefresh
- `access`: string (read-only)
- `refresh`: string
