"""Model-facing side of the record assistant: prompt id, output schema, validation and the
rule-based answers. Pure functions over the collected record: no database and no clock.

The assistant reads the record back. It never judges a result or a food: those questions get the
record and a pointer to the care team."""

from typing import Any

from ai.output_validation import (
    FORBIDDEN,
    NUMBER_PATTERN,
    TIMESTAMP_PATTERN,
    Errors,
    numeric_values,
    schema_errors,
    validation_error,
)
from nutrition.engine import UNITS

CHAT = "patient_chat_v1"
CHAT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer"],
    "properties": {"answer": {"type": "string", "minLength": 1, "maxLength": 3000}},
}
# ponytail: English wording only. Blunt on purpose; an answer that trips it is replaced by the
# rule-based one. Add Arabic terms if a provider is seen giving advice in Arabic.
CHAT_FORBIDDEN = [*FORBIDDEN, "safe to", "safe for you", "you should", "you must", "stop eating", "your dose", "cure"]


def validate_answer(output: Any, payload: dict) -> Errors:
    """No advice wording, and no number that is not in the record or the question."""
    errors = schema_errors(output, CHAT_SCHEMA)
    if errors:
        return errors
    text = output["answer"]
    errors = [
        validation_error("unsupported_clinical_claim", f"Contains wording outside the assistant's role: '{term}'.")
        for term in CHAT_FORBIDDEN
        if term in text.lower()
    ]
    known = numeric_values(payload["record"], with_free_text=True)
    known |= {float(n) for n in NUMBER_PATTERN.findall(payload["question"])}
    invented = sorted({n for n in NUMBER_PATTERN.findall(TIMESTAMP_PATTERN.sub(" ", text)) if float(n) not in known})
    if invented:
        errors.append(validation_error("ungrounded_number", f"Numbers not present in the record: {invented}"))
    return errors


# --- Rule-based answers: the offline provider and the fallback. Templates over the record. ---

# Analyte as stored (lower-case fragment) -> (Arabic name, words a question may use).
_ANALYTES = {
    "urea": ("اليوريا", ["urea", "bun", "يوريا"]),
    "potassium": ("البوتاسيوم", ["potassium", "بوتاسيوم"]),
    "phosph": ("الفوسفات", ["phosph", "فوسف"]),
    "hemoglobin": ("الهيموغلوبين", ["hemoglobin", "haemoglobin", "هيموغلوبين", "هيموجلوبين", "خضاب"]),
    "albumin": ("الألبومين", ["albumin", "ألبومين", "البومين"]),
    "creatinine": ("الكرياتينين", ["creatinine", "كرياتينين"]),
    "sodium": ("الصوديوم", ["sodium", "صوديوم"]),
    "calcium": ("الكالسيوم", ["calcium", "كالسيوم"]),
}
_NUTRIENT_AR = {
    "energy": "الطاقة",
    "protein": "البروتين",
    "sodium": "الصوديوم",
    "potassium": "البوتاسيوم",
    "phosphorus": "الفوسفور",
    "calcium": "الكالسيوم",
    "fluid": "السوائل",
}
_DRINK = ["drink", "tea", "coffee", "water", "juice", "fluid", "شرب", "شاي", "قهوة", "ماء", "عصير", "سوائل"]
_FOOD = [*_DRINK, "eat", "can i", "ok to", "okay to", "allowed", "آكل", "اكل", "أكل", "يمكنني", "مسموح"]
_IDEAS = ["idea", "suggest", "recipe", "اقتراح", "أفكار", "افكار", "وصف"]
# Arabic entries are stems, so possessive and plural forms match too (جلستي، وجباتي).
_MEALS = ["meal", "diary", "ate", "food", "وجب", "طعام"]
_LABS = ["blood", "lab", "test", "result", "تحليل", "تحاليل", "فحص", "مختبر", "نتيجة", "نتائج"]
_SESSIONS = ["session", "appointment", "dialysis", "جلس", "موعد", "غسيل"]


def _lab_line(lab: dict, ar: bool) -> str:
    low, high, day = lab["reference_low"], lab["reference_high"], lab["collected_at"][:10]
    ranged = low is not None and high is not None
    if ar:
        name = next((arabic for key, (arabic, _) in _ANALYTES.items() if key in lab["analyte"].lower()), lab["analyte"])
        line = f"{name}: {lab['value']} {lab['unit']} بتاريخ {day}"
        return line + (f" (النطاق المرجعي للمختبر من {low} إلى {high})" if ranged else "")
    line = f"{lab['analyte']}: {lab['value']} {lab['unit']}, collected {day}"
    return line + (f" (laboratory reference range {low} to {high})" if ranged else "")


def _labs(record: dict, ar: bool, key: str | None = None) -> str:
    labs = record["laboratory_results"]  # oldest first
    care = (
        "أستطيع قراءة النتائج لك، أما معناها لحالتك فيشرحه فريق الرعاية."
        if ar
        else "I can read results back to you; your care team explains what they mean for you."
    )
    if key:
        match = [lab for lab in labs if key in lab["analyte"].lower()]
        if not match:
            name = _ANALYTES[key][0] if ar else _ANALYTES[key][1][0]
            return (
                f"لا توجد في سجلك نتيجة متاحة لتحليل {name}. تظهر النتائج هنا بعد أن يتيحها طبيبك."
                if ar
                else f"I can't find a released {name} result in your record. "
                "Results appear here after your doctor releases them."
            )
        lead = "آخر نتيجة متاحة لك — " if ar else "Your latest released result — "
        return f"{lead}{_lab_line(match[-1], ar)}. {care}"
    if not labs:
        return "لا توجد نتائج مخبرية متاحة في سجلك." if ar else "No laboratory results have been released to you yet."
    latest = [lab for lab in labs if lab["report_id"] == labs[-1]["report_id"]]
    lead = "آخر نتائجك المخبرية المتاحة:" if ar else "Your latest released laboratory results:"
    return "\n".join([lead, *(f"• {_lab_line(lab, ar)}" for lab in latest), care])


def _sessions(record: dict, ar: bool) -> str:
    upcoming, summaries = record["upcoming_sessions"], record["released_summaries"]
    if upcoming:
        text = f"جلستك القادمة مجدولة في {upcoming[0]}." if ar else f"Your next session is scheduled for {upcoming[0]}."
    else:
        text = "لا توجد جلسة قادمة مجدولة في سجلك." if ar else "No upcoming session is scheduled in your record."
    if summaries:
        latest = summaries[0]
        lead = "آخر ملخص أتاحه طبيبك" if ar else "Latest summary released by your doctor"
        text += f"\n{lead} ({latest['session_date']}): {latest['text']}"
    return text


def _plan_lines(plan: dict, ar: bool) -> list[str]:
    lines = [plan["guidance"]] if plan["guidance"] else []
    for key, limit in plan["prescribed_targets"].items():
        nutrient = key.removesuffix("_max")
        name, unit = nutrient.rsplit("_", 1)[0], UNITS.get(nutrient, "")
        lines.append(
            f"• {_NUTRIENT_AR.get(name, name)}: حتى {limit} {unit} لكل وجبة"
            if ar
            else f"• {name}: up to {limit} {unit} per meal"
        )
    if plan["allergies"]:
        lines.append(("الحساسية الموثّقة: " if ar else "Documented allergies: ") + ", ".join(plan["allergies"]))
    return lines


def _meals(record: dict, ar: bool) -> str:
    today = record["diary_today"]
    if not today["meals_recorded"]:
        return "لم تُسجَّل أي وجبة اليوم." if ar else "No meal is recorded for today."
    foods = ", ".join(today["most_recorded_foods"])
    text = (
        f"عدد الوجبات المسجّلة اليوم: {today['meals_recorded']} ({foods})."
        if ar
        else f"Meals recorded today: {today['meals_recorded']} ({foods})."
    )
    fluid = today["daily_average_on_complete_days"].get("fluid_ml")
    if fluid is not None:
        text += f" مجموع السوائل المسجّلة اليوم: {fluid} mL." if ar else f" Fluid recorded today: {fluid} mL."
    return text


def _food(record: dict, ar: bool, drink: bool) -> str:
    plan = record["nutrition_plan"]
    lines = [
        "لا أستطيع أن أقرر إن كان طعام أو شراب مناسباً لك اليوم؛ هذا سؤال لفريق الرعاية. إليك ما في سجلك:"
        if ar
        else "I can't decide whether a food or drink is right for you today; that is a question for your care "
        "team. Here is what your record says:"
    ]
    if plan:
        lines += ["خطتك الغذائية المعتمدة:" if ar else "Your approved nutrition plan:", *_plan_lines(plan, ar)]
    else:
        lines.append(
            "لم يعتمد فريق الرعاية خطة غذائية لك بعد."
            if ar
            else "Your care team has not approved a nutrition plan for you yet."
        )
    lines.append(_meals(record, ar))
    if drink:
        lines.append("المشروبات مثل الشاي تُحسب ضمن السوائل." if ar else "Drinks such as tea count toward your fluid.")
    return "\n".join(lines)


def _ideas(record: dict, ar: bool) -> str:
    ideas = record["approved_meal_ideas"]
    if not ideas:
        return "لا توجد بعد أفكار وجبات اعتمدها طبيبك." if ar else "No meal ideas have been approved for you yet."
    lead = "أفكار وجبات اعتمدها فريق الرعاية لك: " if ar else "Meal ideas your care team approved for you: "
    return lead + ", ".join(idea["name_ar" if ar else "name"] for idea in ideas) + "."


def mock_answer(payload: dict) -> str:
    """Pick the part of the record the question is about. Unknown questions get the overview."""
    record, ar = payload["record"], payload.get("language") == "ar"
    question = payload["question"].lower()

    def has(words: list[str]) -> bool:
        return any(word in question for word in words)

    for key, (_, words) in _ANALYTES.items():
        if has(words):
            return _labs(record, ar, key)
    if has(_FOOD):
        return _food(record, ar, has(_DRINK))
    if has(_IDEAS):
        return _ideas(record, ar)
    if has(_MEALS):
        return _meals(record, ar)
    if has(_LABS):
        return _labs(record, ar)
    if has(_SESSIONS):
        return _sessions(record, ar)
    lead = "هذا ملخص ما في سجلك:" if ar else "Here is a summary of your record:"
    return "\n\n".join([lead, _sessions(record, ar), _labs(record, ar), _meals(record, ar), _ideas(record, ar)])
