# API examples

Real responses recorded against the seeded demo database (`seed_demo --approve-facts`, mock LLM).
Lists are paginated (`count`, `next`, `previous`, `results`, 20 per page); long lists are cut to
one item here. Send `Authorization: Bearer <access>` on every call except the two auth calls.

## POST /api/v1/auth/token

Log in — as `anonymous` → **200**

Request:
```json
{
  "username": "nurse1",
  "password": "demo-password-here"
}
```
Response:
```json
{
  "refresh": "<jwt>",
  "access": "<jwt>",
  "role": "nurse",
  "patient_id": null
}
```
`role` and `patient_id` are also inside the JWT claims. The password shown is whatever `DEMO_PASSWORD` was.

## POST /api/v1/auth/token/refresh

Refresh the access token — as `anonymous` → **200**

Request:
```json
{
  "refresh": "<jwt>"
}
```
Response:
```json
{
  "access": "<jwt>"
}
```

## GET /api/v1/patients/

List patients — as `nurse` → **200**

Response:
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "code": "SYN-001",
      "display_name_ar": "مريضة تجريبية (أ)",
      "birth_year": 1958,
      "is_synthetic": true,
      "created_at": "2026-10-05T16:05:11.823178+03:00",
      "attention_flag_count": 5
    }
  ]
}
```

## GET /api/v1/patients/1/

One patient — as `doctor` → **200**

Response:
```json
{
  "id": 1,
  "code": "SYN-001",
  "display_name_ar": "مريضة تجريبية (أ)",
  "birth_year": 1958,
  "is_synthetic": true,
  "created_at": "2026-10-05T16:05:11.823178+03:00",
  "attention_flag_count": 5
}
```

## GET /api/v1/patients/1/timeline/

Timeline, newest first — as `doctor` → **200**

Response:
```json
{
  "count": 15,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 15,
      "patient": 1,
      "session_date": "2026-09-30",
      "start_time": "08:00:00",
      "end_time": "12:00:00",
      "pre_sbp": 144,
      "pre_dbp": 85,
      "post_sbp": 118,
      "post_dbp": 68,
      "min_intra_sbp": 104,
      "pre_weight_kg": "60.8",
      "post_weight_kg": "58.4",
      "uf_volume_ml": 2400,
      "access_type": "AVF",
      "created_by": 1,
      "created_at": "2026-10-05T16:05:12.882625+03:00",
      "notes": [
        {
          "id": 15,
          "session": 15,
          "author": 1,
          "text_ar": "نفس الحالة، برد ورجفة قوية بالساعة الثالثة ودوخة خفيفة، نزلنا السحب وخبرنا الطبيب المقيم.",
          "created_at": "2026-10-05T16:05:12.883303+03:00",
          "supersedes": null
        }
      ],
      "facts": {
        "symptoms": [
          {
            "code": "chills",
            "label_ar": "برد ورجفة قوية",
            "timing": "intra",
            "evidence_span": "برد ورجفة قوية بالساعة الثالثة",
            "note_id": 15
          },
          {
            "code": "dizziness",
            "label_ar": "دوخة خفيفة",
            "timing": "intra",
            "evidence_span": "دوخة خفيفة",
            "note_id": 15
          }
        ],
        "access_findings": [],
        "staff_actions": [
          {
            "description_ar": "تقليل السحب",
            "evidence_span": "نزلنا السحب",
            "note_id": 15
          },
          {
            "description_ar": "إبلاغ الطبيب المقيم",
            "evidence_span": "خبرنا الطبيب المقيم",
            "note_id": 15
          }
        ],
        "updated_at": "2026-10-05T16:05:12.884868+03:00"
      },
      "flags": [
        {
          "id": 5,
          "patient": 1,
          "session": 15,
          "rule_id": "R2_RECURRING_SYMPTOM",
          "severity": "attention",
          "message_ar": "تكرر العرَض «رجفة/برد» في ٣ من آخر ٥ جلسات موثَّقة",
          "evidence": {
            "code": "chills",
            "session_ids": [
              11,
              13
            ],
            "note_ids": [
              11,
              13
            ],
            "count": 3,
            "window_sessions": 5,
            "minimum": 3,
            "window": 5
          },
          "created_at": "2026-10-05T16:05:12.895770+03:00",
          "rules_version": "285a7ffa611f4870"
        },
        {
          "id": 4,
          "patient": 1,
          "session": 15,
          "rule_id": "R1_INTRA_SBP_DROP",
          "severity": "attention",
          "message_ar": "انخفاض ضغط الدم الانقباضي أثناء الجلسة بمقدار ٤٠ ملم زئبق (من ١٤٤ إلى ١٠٤)",
          "evidence": {
            "session_ids": [
              15
            ],
            "note_ids": [
              15
            ],
            "pre_sbp": 144,
            "low_sbp": 104,
            "low_source": "min_intra_sbp",
            "used_fallback": false,
            "drop_mmhg": 40,
            "threshold_mmhg": 20
          },
          "created_at": "2026-10-05T16:05:12.895754+03:00",
          "rules_version": "285a7ffa611f4870"
        }
      ]
    }
  ]
}
```

## GET /api/v1/patients/2/flags/

Flags for a patient — as `nurse` → **200**

Response:
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "patient": 2,
      "session": 30,
      "rule_id": "R5_RECURRING_ACCESS_ISSUE",
      "severity": "attention",
      "message_ar": "تكرر ملاحظة المدخل الوعائي «نزف» في ٢ من آخر ٣ جلسات موثَّقة",
      "evidence": {
        "code": "bleeding",
        "session_ids": [
          28,
          30
        ],
        "note_ids": [
          29,
          31
        ],
        "count": 2,
        "window_sessions": 3,
        "minimum": 2,
        "window": 3
      },
      "created_at": "2026-10-05T16:05:12.946872+03:00",
      "rules_version": "285a7ffa611f4870"
    }
  ]
}
```

## POST /api/v1/patients/1/sessions/

Create a session (all vitals optional except times and access type) — as `nurse` → **201**

Request:
```json
{
  "session_date": "2026-10-03",
  "start_time": "08:00",
  "end_time": "12:00",
  "pre_sbp": 141,
  "pre_dbp": 84,
  "post_sbp": 128,
  "post_dbp": 79,
  "min_intra_sbp": 126,
  "pre_weight_kg": "60.5",
  "post_weight_kg": "58.3",
  "uf_volume_ml": 2200,
  "access_type": "AVF"
}
```
Response:
```json
{
  "id": 46,
  "patient": 1,
  "session_date": "2026-10-03",
  "start_time": "08:00:00",
  "end_time": "12:00:00",
  "pre_sbp": 141,
  "pre_dbp": 84,
  "post_sbp": 128,
  "post_dbp": 79,
  "min_intra_sbp": 126,
  "pre_weight_kg": "60.5",
  "post_weight_kg": "58.3",
  "uf_volume_ml": 2200,
  "access_type": "AVF",
  "created_by": 1,
  "created_at": "2026-10-05T16:05:14.643474+03:00"
}
```

## POST /api/v1/patients/1/sessions/

Validation error (shared error format) — as `nurse` → **400**

Request:
```json
{
  "session_date": "2026-10-04",
  "start_time": "12:00",
  "end_time": "08:00",
  "pre_sbp": 1200,
  "access_type": "AVF"
}
```
Response:
```json
{
  "error": {
    "code": "validation_error",
    "message_ar": "البيانات المدخلة غير صحيحة.",
    "message_en": "Invalid input.",
    "details": {
      "pre_sbp": [
        "تأكد ان القيمة أقل من أو تساوي 260."
      ]
    }
  }
}
```

## GET /api/v1/sessions/46/

One session — as `nurse` → **200**

Response:
```json
{
  "id": 46,
  "patient": 1,
  "session_date": "2026-10-03",
  "start_time": "08:00:00",
  "end_time": "12:00:00",
  "pre_sbp": 141,
  "pre_dbp": 84,
  "post_sbp": 128,
  "post_dbp": 79,
  "min_intra_sbp": 126,
  "pre_weight_kg": "60.5",
  "post_weight_kg": "58.3",
  "uf_volume_ml": 2200,
  "access_type": "AVF",
  "created_by": 1,
  "created_at": "2026-10-05T16:05:14.643474+03:00"
}
```

## POST /api/v1/sessions/46/notes/

Create a note; extraction runs immediately and returns the draft id/status — as `nurse` → **201**

Request:
```json
{
  "text_ar": "الجلسة مشت زينة وماكو شكوى."
}
```
Response:
```json
{
  "id": 47,
  "session": 46,
  "author": 1,
  "text_ar": "الجلسة مشت زينة وماكو شكوى.",
  "created_at": "2026-10-05T16:05:14.662807+03:00",
  "supersedes": null,
  "draft_id": 47,
  "draft_status": "pending"
}
```

## GET /api/v1/notes/47/

One note — as `doctor` → **200**

Response:
```json
{
  "id": 47,
  "session": 46,
  "author": 1,
  "text_ar": "الجلسة مشت زينة وماكو شكوى.",
  "created_at": "2026-10-05T16:05:14.662807+03:00",
  "supersedes": null
}
```

## GET /api/v1/extraction-drafts/?status=pending

Drafts filtered by status — as `nurse` → **200**

Response:
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 47,
      "note": 47,
      "note_text_ar": "الجلسة مشت زينة وماكو شكوى.",
      "session": 46,
      "payload": {
        "symptoms": [],
        "access_findings": [],
        "staff_actions": [],
        "mentioned_values": [],
        "missing_info": [],
        "uncertain": []
      },
      "edited_payload": null,
      "status": "pending",
      "validation_errors": [],
      "model_name": "mock",
      "prompt_version": "extraction_v1",
      "created_at": "2026-10-05T16:05:14.681559+03:00",
      "reviewed_by": null,
      "reviewed_at": null
    }
  ]
}
```

## GET /api/v1/extraction-drafts/47/

One draft — as `nurse` → **200**

Response:
```json
{
  "id": 47,
  "note": 47,
  "note_text_ar": "الجلسة مشت زينة وماكو شكوى.",
  "session": 46,
  "payload": {
    "symptoms": [],
    "access_findings": [],
    "staff_actions": [],
    "mentioned_values": [],
    "missing_info": [],
    "uncertain": []
  },
  "edited_payload": null,
  "status": "pending",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "extraction_v1",
  "created_at": "2026-10-05T16:05:14.681559+03:00",
  "reviewed_by": null,
  "reviewed_at": null
}
```

## POST /api/v1/extraction-drafts/47/approve/

Approve as-is (body optional). To edit first, send `edited_payload` (full extraction_v1 object) — as `nurse` → **200**

Request:
```json
{}
```
Response:
```json
{
  "id": 47,
  "note": 47,
  "note_text_ar": "الجلسة مشت زينة وماكو شكوى.",
  "session": 46,
  "payload": {
    "symptoms": [],
    "access_findings": [],
    "staff_actions": [],
    "mentioned_values": [],
    "missing_info": [],
    "uncertain": []
  },
  "edited_payload": null,
  "status": "approved",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "extraction_v1",
  "created_at": "2026-10-05T16:05:14.681559+03:00",
  "reviewed_by": 1,
  "reviewed_at": "2026-10-05T16:05:14.703723+03:00"
}
```

## POST /api/v1/extraction-drafts/47/approve/

Approving twice conflicts — as `nurse` → **409**

Request:
```json
{}
```
Response:
```json
{
  "error": {
    "code": "invalid_state",
    "message_ar": "حالة المسودة الحالية لا تسمح بهذا الإجراء.",
    "message_en": "Draft is 'approved'; this action needs one of: pending.",
    "details": {
      "status": "approved"
    }
  }
}
```

## POST /api/v1/sessions/46/notes/

(second note for the reject/retry examples) — as `nurse` → **201**

Request:
```json
{
  "text_ar": "ملاحظة إضافية: المريضة مرتاحة."
}
```
Response:
```json
{
  "id": 48,
  "session": 46,
  "author": 1,
  "text_ar": "ملاحظة إضافية: المريضة مرتاحة.",
  "created_at": "2026-10-05T16:05:14.718822+03:00",
  "supersedes": null,
  "draft_id": 48,
  "draft_status": "pending"
}
```

## POST /api/v1/extraction-drafts/48/reject/

Reject (allowed from pending or invalid) — as `nurse` → **200**

Request:
```json
{
  "reason": "غير مطلوب"
}
```
Response:
```json
{
  "id": 48,
  "note": 48,
  "note_text_ar": "ملاحظة إضافية: المريضة مرتاحة.",
  "session": 46,
  "payload": {
    "symptoms": [],
    "access_findings": [],
    "staff_actions": [],
    "mentioned_values": [],
    "missing_info": [],
    "uncertain": []
  },
  "edited_payload": null,
  "status": "rejected",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "extraction_v1",
  "created_at": "2026-10-05T16:05:14.723110+03:00",
  "reviewed_by": 1,
  "reviewed_at": "2026-10-05T16:05:14.738238+03:00"
}
```

## POST /api/v1/extraction-drafts/48/retry/

Retry: closes the old draft and returns a NEW draft — as `nurse` → **201**

Response:
```json
{
  "id": 49,
  "note": 48,
  "note_text_ar": "ملاحظة إضافية: المريضة مرتاحة.",
  "session": 46,
  "payload": {
    "symptoms": [],
    "access_findings": [],
    "staff_actions": [],
    "mentioned_values": [],
    "missing_info": [],
    "uncertain": []
  },
  "edited_payload": null,
  "status": "pending",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "extraction_v1",
  "created_at": "2026-10-05T16:05:14.751091+03:00",
  "reviewed_by": null,
  "reviewed_at": null
}
```

## POST /api/v1/patients/1/summaries/

Request a summary (status is `draft`, or `invalid` with `validation_errors`) — as `doctor` → **201**

Request:
```json
{
  "audience": "patient",
  "period_start": "2026-09-20",
  "period_end": "2026-09-30"
}
```
Response:
```json
{
  "id": 1,
  "patient": 1,
  "audience": "patient",
  "period_start": "2026-09-20",
  "period_end": "2026-09-30",
  "sentences": [
    {
      "text_ar": "في جلسة 2026-09-21 وُثِّق: رجفة وبرد، إيقاف السحب مؤقتاً.",
      "citations": [
        11
      ]
    },
    {
      "text_ar": "في جلسة 2026-09-26 وُثِّق: رجفة وبرد، إعطاء مغذي.",
      "citations": [
        13
      ]
    }
  ],
  "status": "draft",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "summary_patient_v1",
  "created_at": "2026-10-05T16:05:14.769763+03:00",
  "approved_by": null,
  "approved_at": null
}
```

## GET /api/v1/summaries/1/

One summary — as `nurse` → **200**

Response:
```json
{
  "id": 1,
  "patient": 1,
  "audience": "patient",
  "period_start": "2026-09-20",
  "period_end": "2026-09-30",
  "sentences": [
    {
      "text_ar": "في جلسة 2026-09-21 وُثِّق: رجفة وبرد، إيقاف السحب مؤقتاً.",
      "citations": [
        11
      ]
    },
    {
      "text_ar": "في جلسة 2026-09-26 وُثِّق: رجفة وبرد، إعطاء مغذي.",
      "citations": [
        13
      ]
    }
  ],
  "status": "draft",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "summary_patient_v1",
  "created_at": "2026-10-05T16:05:14.769763+03:00",
  "approved_by": null,
  "approved_at": null
}
```

## GET /api/v1/summaries/1/

Patient cannot see an unapproved summary — as `patient` → **404**

Response:
```json
{
  "error": {
    "code": "error",
    "message_ar": "العنصر غير موجود.",
    "message_en": "No Summary matches the given query.",
    "details": {}
  }
}
```

## POST /api/v1/summaries/1/approve/

Approve (doctor only, from `draft`) — as `doctor` → **200**

Response:
```json
{
  "id": 1,
  "patient": 1,
  "audience": "patient",
  "period_start": "2026-09-20",
  "period_end": "2026-09-30",
  "sentences": [
    {
      "text_ar": "في جلسة 2026-09-21 وُثِّق: رجفة وبرد، إيقاف السحب مؤقتاً.",
      "citations": [
        11
      ]
    },
    {
      "text_ar": "في جلسة 2026-09-26 وُثِّق: رجفة وبرد، إعطاء مغذي.",
      "citations": [
        13
      ]
    }
  ],
  "status": "approved",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "summary_patient_v1",
  "created_at": "2026-10-05T16:05:14.769763+03:00",
  "approved_by": 2,
  "approved_at": "2026-10-05T16:05:14.781851+03:00"
}
```

## GET /api/v1/me/summaries/

Patient's own approved summaries — as `patient` → **200**

Response:
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "patient": 1,
      "audience": "patient",
      "period_start": "2026-09-20",
      "period_end": "2026-09-30",
      "sentences": [
        {
          "text_ar": "في جلسة 2026-09-21 وُثِّق: رجفة وبرد، إيقاف السحب مؤقتاً.",
          "citations": [
            11
          ]
        },
        {
          "text_ar": "في جلسة 2026-09-26 وُثِّق: رجفة وبرد، إعطاء مغذي.",
          "citations": [
            13
          ]
        }
      ],
      "status": "approved",
      "validation_errors": [],
      "model_name": "mock",
      "prompt_version": "summary_patient_v1",
      "created_at": "2026-10-05T16:05:14.769763+03:00",
      "approved_by": 2,
      "approved_at": "2026-10-05T16:05:14.781851+03:00"
    }
  ]
}
```

## POST /api/v1/patients/1/summaries/

(second summary for the reject example) — as `doctor` → **201**

Request:
```json
{
  "audience": "clinician",
  "period_start": "2026-09-20",
  "period_end": "2026-09-30"
}
```
Response:
```json
{
  "id": 2,
  "patient": 1,
  "audience": "clinician",
  "period_start": "2026-09-20",
  "period_end": "2026-09-30",
  "sentences": [
    {
      "text_ar": "في جلسة 2026-09-21 وُثِّق: رجفة وبرد، إيقاف السحب مؤقتاً.",
      "citations": [
        11
      ]
    },
    {
      "text_ar": "في جلسة 2026-09-26 وُثِّق: رجفة وبرد، إعطاء مغذي.",
      "citations": [
        13
      ]
    }
  ],
  "status": "draft",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "summary_clinician_v1",
  "created_at": "2026-10-05T16:05:14.795733+03:00",
  "approved_by": null,
  "approved_at": null
}
```

## POST /api/v1/summaries/2/reject/

Reject (doctor only, from `draft`) — as `doctor` → **200**

Request:
```json
{
  "reason": "يحتاج مراجعة"
}
```
Response:
```json
{
  "id": 2,
  "patient": 1,
  "audience": "clinician",
  "period_start": "2026-09-20",
  "period_end": "2026-09-30",
  "sentences": [
    {
      "text_ar": "في جلسة 2026-09-21 وُثِّق: رجفة وبرد، إيقاف السحب مؤقتاً.",
      "citations": [
        11
      ]
    },
    {
      "text_ar": "في جلسة 2026-09-26 وُثِّق: رجفة وبرد، إعطاء مغذي.",
      "citations": [
        13
      ]
    }
  ],
  "status": "rejected",
  "validation_errors": [],
  "model_name": "mock",
  "prompt_version": "summary_clinician_v1",
  "created_at": "2026-10-05T16:05:14.795733+03:00",
  "approved_by": null,
  "approved_at": null
}
```

## GET /api/v1/audit/?object_type=ExtractionDraft&object_id=47

Audit trail for one object — as `admin` → **200**

Response:
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 4,
      "actor": 1,
      "action": "approve_draft",
      "object_type": "ExtractionDraft",
      "object_id": 47,
      "before": {
        "payload": {
          "symptoms": [],
          "access_findings": [],
          "staff_actions": [],
          "mentioned_values": [],
          "missing_info": [],
          "uncertain": []
        },
        "edited_payload": null,
        "status": "pending",
        "validation_errors": [],
        "reviewed_by": null,
        "reviewed_at": null
      },
      "after": {
        "payload": {
          "symptoms": [],
          "access_findings": [],
          "staff_actions": [],
          "mentioned_values": [],
          "missing_info": [],
          "uncertain": []
        },
        "edited_payload": null,
        "status": "approved",
        "validation_errors": [],
        "reviewed_by": 1,
        "reviewed_at": "2026-10-05T13:05:14.703Z"
      },
      "created_at": "2026-10-05T16:05:14.706342+03:00"
    }
  ]
}
```

## GET /api/v1/patients/

Wrong role — as `patient` → **403**

Response:
```json
{
  "error": {
    "code": "permission_denied",
    "message_ar": "ليست لديك صلاحية لهذا الإجراء.",
    "message_en": "ليس لديك صلاحية للقيام بهذا الإجراء.",
    "details": {}
  }
}
```

