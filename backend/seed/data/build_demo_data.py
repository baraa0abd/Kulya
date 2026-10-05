"""Builds seed/data/demo.json: 3 synthetic patients x 15 sessions with Iraqi-dialect notes and the
expected (hand-written) extraction for each note. Entirely invented; no real person or record.

    cd backend && python seed/data/build_demo_data.py

Storylines (see docs/demo_data.md):
  SYN-001  recurring chills + intradialytic SBP drops in later sessions  -> R1, R2
  SYN-002  access bleeding in 2 of the last 3 sessions + one high interdialytic gain -> R4, R5
  SYN-003  stable, two incomplete records -> R3 only
"""

import datetime as dt
import json
from pathlib import Path

START = dt.date(2026, 8, 29)  # a Saturday; sessions run Sat / Mon / Wed for five weeks
DATES = [START + dt.timedelta(weeks=w, days=d) for w in range(5) for d in (0, 2, 4)]
KEYS = ["symptoms", "access_findings", "staff_actions", "mentioned_values", "missing_info", "uncertain"]


def S(code, label, timing, span):
    return ("symptoms", {"code": code, "label_ar": label, "timing": timing, "evidence_span": span})


def A(code, label, span):
    return ("access_findings", {"code": code, "label_ar": label, "evidence_span": span})


def ACT(desc, span):
    return ("staff_actions", {"description_ar": desc, "evidence_span": span})


def V(kind, raw):
    return ("mentioned_values", {"kind": kind, "raw_text": raw})


def M(field, reason):
    return ("missing_info", {"field": field, "reason_ar": reason})


def U(text, reason):
    return ("uncertain", {"text": text, "reason_ar": reason})


def note(text, *items, superseded=False):
    expected = {k: [] for k in KEYS}
    for key, item in items:
        expected[key].append(item)
    return {"text_ar": text, "expected": expected, "superseded": superseded}


NUMBERS_ONLY = "قيمة مذكورة بدون رقم؛ القيم تؤخذ من الحقول الرقمية فقط"

SYN_001_NOTES = [
    [note("الجلسة مشت زينة والمريضة مرتاحة، ماكو شكوى.")],
    [note("المريضة اجت بوقتها، الجلسة كملت طبيعي وما اشتكت من شي.")],
    [note("جلسة هادئة، الفستولا تشتغل زين والمريضة نامت شوية.")],
    [note("ماكو مشاكل اليوم، كملنا الجلسة للآخر.")],
    [
        note(
            "المريضة تكول تعبانة شوية بعد الجلسة، كعدت ربع ساعة وبعدين راحت.",
            S("fatigue", "تعب بعد الجلسة", "post", "تعبانة شوية بعد الجلسة"),
        )
    ],
    [note("الجلسة طبيعيه، ما عدها رجفة ولا دوخة.")],
    [note("كلشي تمام اليوم، الضغط ثابت والمريضة مرتاحة.")],
    [
        note(
            "المريضة كالت تحس ببرد بنص الجلسة، غطيناها ببطانية وكملت الجلسة.",
            S("chills", "إحساس بالبرد", "intra", "تحس ببرد بنص الجلسة"),
            ACT("تغطية المريضة ببطانية", "غطيناها ببطانية"),
        )
    ],
    [note("جلسة اعتيادية، ماكو شكوى والوزن نزل مثل المطلوب.")],
    [
        note(
            "الضغط نزل بآخر ساعة والمريضة حست بدوخة، رفعنا رجليها وتحسنت.",
            S("dizziness", "دوخة", "intra", "حست بدوخة"),
            ACT("رفع رجلي المريضة", "رفعنا رجليها"),
            U("الضغط نزل بآخر ساعة", NUMBERS_ONLY),
        )
    ],
    [
        note(
            "صارت عدها رجفه وبرد بعد ساعتين من البداية والضغط نزل، وقفنا السحب شوية ورجعناه.",
            S("chills", "رجفة وبرد", "intra", "صارت عدها رجفه وبرد بعد ساعتين من البداية"),
            ACT("إيقاف السحب مؤقتاً", "وقفنا السحب شوية"),
            U("والضغط نزل", NUMBERS_ONLY),
        )
    ],
    [note("اليوم أحسن، ماكو رجفة والمريضة كملت الجلسة مرتاحة.")],
    [
        note(
            "رجعت الرجفة اليوم هم، المريضة ترجف وتكول بردانة، الضغط صار ٩٥ على ٦٠ بنص الجلسة، انطيناها مغذي ١٠٠ مل.",
            S("chills", "رجفة وبرد", "intra", "المريضة ترجف وتكول بردانة"),
            ACT("إعطاء مغذي", "انطيناها مغذي ١٠٠ مل"),
            V("bp", "٩٥ على ٦٠"),
            V("other", "١٠٠ مل"),
        )
    ],
    [
        note(
            "الجلسة مشت بدون مشاكل، بس المريضة خايفة ترجع الرجفة.",
            U("خايفة ترجع الرجفة", "قلق من تكرار العرَض وليس عرَضاً موثَّقاً في هذه الجلسة"),
        )
    ],
    [
        note(
            "نفس الحالة، برد ورجفة قوية بالساعة الثالثة ودوخة خفيفة، نزلنا السحب وخبرنا الطبيب المقيم.",
            S("chills", "برد ورجفة قوية", "intra", "برد ورجفة قوية بالساعة الثالثة"),
            S("dizziness", "دوخة خفيفة", "intra", "دوخة خفيفة"),
            ACT("تقليل السحب", "نزلنا السحب"),
            ACT("إبلاغ الطبيب المقيم", "خبرنا الطبيب المقيم"),
        )
    ],
]

SYN_002_NOTES = [
    [note("الجلسة طبيعية والمريض ما اشتكى من شي.")],
    [note("المريض مرتاح اليوم، الجلسة كملت بدون مشاكل.")],
    [note("ماكو شكوى، الفستولا زينة والجريان ممتاز.")],
    [note("جلسة اعتيادية، المريض ياكل ويسولف طبيعي.")],
    [
        note(
            "المريض عنده حكة بالجلد من يومين، ماكو شي ثاني.",
            S("itching", "حكة في الجلد", "pre", "حكة بالجلد من يومين"),
        )
    ],
    [note("الجلسه مشت زينه، ماكو شي يذكر.")],
    [note("المريض نام اغلب الجلسة، كلشي طبيعي.")],
    [note("ماكو مشاكل، شلنا الابر والمريض طلع ماشي.")],
    [
        note(
            "المريض اجه وزنه زايد هواية عن الجلسة الفاتت، يكول شرب مي هواية بالعزيمة، وعنده ضيق نفس خفيف قبل الجلسة.",
            S("shortness_of_breath", "ضيق نفس خفيف", "pre", "ضيق نفس خفيف قبل الجلسة"),
            U("وزنه زايد هواية عن الجلسة الفاتت", NUMBERS_ONLY),
        )
    ],
    [
        note(
            "المريض اشتكى من صداع بنص الجلسة.",
            S("headache", "صداع", "intra", "صداع بنص الجلسة"),
            superseded=True,
        ),
        note(
            "تصحيح: الصداع جان قبل الجلسة مو بنصها، وراح من نفسه بدون علاج.",
            S("headache", "صداع قبل الجلسة", "pre", "الصداع جان قبل الجلسة"),
        ),
    ],
    [note("اليوم وزنه زين، ملتزم بالسوائل هالمرة والجلسة طبيعية.")],
    [note("جلسة هادئة وماكو شكوى.")],
    [
        note(
            "بعد الجلسة صار نزف من مكان الابرة وطول شوية، ضغطنا عليه ربع ساعة ووكف.",
            A("bleeding", "نزف من موضع الإبرة", "صار نزف من مكان الابرة"),
            ACT("الضغط على موضع النزف", "ضغطنا عليه ربع ساعة"),
        )
    ],
    [
        note(
            "اليوم الجريان ضعيف شوية بالبداية، عدلنا مكان الابرة وصار زين.",
            A("poor_flow", "ضعف الجريان في البداية", "الجريان ضعيف شوية بالبداية"),
            ACT("تعديل موضع الإبرة", "عدلنا مكان الابرة"),
        )
    ],
    [
        note(
            "هم اليوم نزف من الفستولا بعد ما شلنا الابر، وأكو ورم خفيف يم مكان الابرة.",
            A("bleeding", "نزف من الفستولا", "نزف من الفستولا بعد ما شلنا الابر"),
            A("swelling", "تورم خفيف قرب موضع الإبرة", "ورم خفيف يم مكان الابرة"),
        )
    ],
]

SYN_003_NOTES = [
    [note("الجلسة مشت زينة، القسطرة تشتغل طبيعي وماكو شكوى.")],
    [note("المريضة مرتاحة، ماكو شي جديد.")],
    [note("الوزن اليوم ٦٢٫٩ كيلو قبل الجلسة مثل ما مسجل، والجلسة طبيعية.", V("weight", "٦٢٫٩ كيلو"))],
    [
        note(
            "المريضة طلعت مستعجلة بعد الجلسة وما لحكنا ناخذ الوزن.",
            M("post_weight_kg", "تذكر الملاحظة أن الوزن بعد الجلسة لم يؤخذ"),
        )
    ],
    [note("جلسة طبيعية، غيرنا ضماد القسطرة ومكانها نظيف.", ACT("تغيير ضماد القسطرة", "غيرنا ضماد القسطرة"))],
    [note("ما عدها رجفة ولا دوخة، الجلسة زينة.")],
    [note("كلشي طبيعي والمريضة تسولف ويانه طول الجلسة.")],
    [note("ماكو شكوى اليوم.")],
    [note("الجلسه كملت بوقتها، المريضه مرتاحه.")],
    [note("جلسة اعتيادية، القسطرة نظيفة وماكو احمرار.")],
    [
        note(
            "جهاز الضغط عطل بآخر الجلسة، ما كدرنا نقيس الضغط بعد الجلسة.",
            M("post_sbp", "تذكر الملاحظة أن الضغط بعد الجلسة لم يُقَس"),
            M("post_dbp", "تذكر الملاحظة أن الضغط بعد الجلسة لم يُقَس"),
        )
    ],
    [note("رجعنا نقيس الضغط بجهاز ثاني اليوم، كلشي طبيعي.")],
    [note("المريضة مرتاحة وماكو شي يذكر.")],
    [note("غيرنا ضماد القسطرة، الجلسة طبيعية.", ACT("تغيير ضماد القسطرة", "غيرنا ضماد القسطرة"))],
    [note("جلسة زينة، ماكو شكوى والمريضة راضية.")],
]

N = None
PATIENTS = [
    {
        "code": "SYN-001",
        "display_name_ar": "مريضة تجريبية (أ)",
        "birth_year": 1958,
        "access_type": "AVF",
        "times": ("08:00", "12:00"),
        "pre_sbp": [138, 142, 136, 140, 144, 139, 141, 137, 143, 142, 145, 138, 140, 136, 144],
        "intra_drop": [10, 11, 9, 10, 11, 10, 11, 9, 11, 30, 27, 12, 45, 14, 40],
        "post_drop": [8, 8, 7, 8, 9, 8, 8, 7, 9, 18, 19, 8, 28, 10, 26],
        "pre_dbp": [82, 85, 80, 84, 86, 83, 84, 81, 85, 84, 86, 82, 83, 80, 85],
        "post_dbp": [78, 80, 76, 79, 81, 78, 79, 77, 80, 72, 74, 77, 64, 75, 68],
        "first_pre_weight": 60.3,
        "post_weight": [58.2, 58.0, 58.1, 58.0, 58.3, 58.1, 58.0, 58.2, 58.1, 58.4, 58.3, 58.1, 58.5, 58.2, 58.4],
        "gain": [N, 2.1, 1.8, 2.4, 1.9, 2.2, 2.6, 1.7, 2.3, 2.5, 2.0, 2.4, 2.2, 1.9, 2.6],
        "notes": SYN_001_NOTES,
    },
    {
        "code": "SYN-002",
        "display_name_ar": "مريض تجريبي (ب)",
        "birth_year": 1965,
        "access_type": "AVF",
        "times": ("08:30", "12:30"),
        "pre_sbp": [150, 148, 152, 146, 149, 151, 147, 150, 158, 149, 148, 151, 147, 150, 149],
        "intra_drop": [12, 10, N, 11, 13, 12, N, 10, 15, 12, 11, N, 13, 12, 14],
        "post_drop": [8, 7, 9, 6, 8, 9, 7, 8, 12, 8, 7, 9, 8, 8, 9],
        "pre_dbp": [88, 86, 90, 85, 87, 89, 86, 88, 92, 87, 86, 89, 86, 88, 87],
        "post_dbp": [82, 81, 84, 80, 82, 83, 81, 82, 85, 82, 81, 83, 81, 82, 82],
        "first_pre_weight": 76.3,
        "post_weight": [74.2, 74.0, 74.3, 74.1, 74.0, 74.2, 74.1, 74.0, 74.6, 74.2, 74.1, 74.0, 74.2, 74.1, 74.3],
        "gain": [N, 2.0, 2.3, 1.8, 2.2, 2.5, 1.9, 2.4, 3.6, 2.1, 2.0, 2.3, 1.8, 2.2, 2.0],
        "notes": SYN_002_NOTES,
    },
    {
        "code": "SYN-003",
        "display_name_ar": "مريضة تجريبية (ج)",
        "birth_year": 1971,
        "access_type": "CVC",
        "times": ("13:00", "17:00"),
        "pre_sbp": [128, 130, 126, 129, 131, 127, 130, 128, 129, 131, 127, 130, 128, 129, 130],
        "intra_drop": [8, 9, 7, N, 10, 8, 9, 7, N, 9, 8, 10, 7, 9, 8],
        "post_drop": [5, 6, 4, 6, 7, 5, 6, 4, 6, 7, N, 6, 5, 6, 5],  # session 11: post BP not measured
        "pre_dbp": [78, 80, 76, 79, 80, 77, 79, 78, 79, 80, 77, 79, 78, 79, 80],
        "post_dbp": [75, 76, 73, 75, 76, 74, 75, 75, 75, 76, N, 75, 75, 75, 76],
        "first_pre_weight": 63.0,
        "post_weight": [61.2, 61.0, 61.1, N, 61.0, 61.2, 61.1, 61.0, 61.2, 61.1, 61.0, 61.2, 61.1, 61.0, 61.1],
        "gain": [N, 1.6, 1.9, 1.5, N, 1.7, 1.8, 1.6, 2.0, 1.7, 1.9, 1.6, 1.8, 1.7, 1.9],
        "pre_weight_override": {4: 62.8},  # session 5: previous post weight was never taken
        "notes": SYN_003_NOTES,
    },
]


def build() -> dict:
    patients = []
    for p in PATIENTS:
        sessions = []
        for i, date in enumerate(DATES):
            pre_sbp = p["pre_sbp"][i]
            if i == 0:
                pre_weight = p["first_pre_weight"]
            elif i in p.get("pre_weight_override", {}):
                pre_weight = p["pre_weight_override"][i]
            else:
                pre_weight = round(p["post_weight"][i - 1] + p["gain"][i], 1)
            post_weight = p["post_weight"][i]
            sessions.append(
                {
                    "session_date": date.isoformat(),
                    "start_time": p["times"][0],
                    "end_time": p["times"][1],
                    "pre_sbp": pre_sbp,
                    "pre_dbp": p["pre_dbp"][i],
                    "post_sbp": None if p["post_drop"][i] is None else pre_sbp - p["post_drop"][i],
                    "post_dbp": p["post_dbp"][i],
                    "min_intra_sbp": None if p["intra_drop"][i] is None else pre_sbp - p["intra_drop"][i],
                    "pre_weight_kg": pre_weight,
                    "post_weight_kg": post_weight,
                    "uf_volume_ml": None if post_weight is None else round((pre_weight - post_weight) * 1000),
                    "access_type": p["access_type"],
                    "notes": p["notes"][i],
                }
            )
        patients.append(
            {
                "code": p["code"],
                "display_name_ar": p["display_name_ar"],
                "birth_year": p["birth_year"],
                "sessions": sessions,
            }
        )
    return {"synthetic": True, "patients": patients}


if __name__ == "__main__":
    out = Path(__file__).parent / "demo.json"
    out.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}")
