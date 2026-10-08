"use client";

import { useEffect, useSyncExternalStore } from "react";

/**
 * Arabic-first interface. Source strings are English; `tr()` returns the Arabic text when the
 * locale is "ar" (the default) and the source string otherwise. A string with no entry falls back
 * to English, so nothing ever renders empty. Text that comes from the server (record content,
 * AI drafts, finding descriptions, error messages) is shown as stored and is not translated here.
 */
export type Locale = "ar" | "en";
const STORAGE_KEY = "copilot.locale";

const AR: Record<string, string> = {
  // --- shell, auth ---
  "Dialysis Copilot": "مساعد الغسيل الكلوي",
  "Synthetic demonstration data": "بيانات تجريبية مصطنعة",
  "Sign out": "تسجيل الخروج",
  "Sign in": "تسجيل الدخول",
  "Sign in. This demonstration runs on synthetic data only and is not a medical device.":
    "سجّل الدخول. هذا العرض يعمل على بيانات مصطنعة فقط وليس جهازاً طبياً.",
  Username: "اسم المستخدم",
  Password: "كلمة المرور",
  "← Back": "→ رجوع",
  "Loading…": "جارٍ التحميل…",
  "Saving…": "جارٍ الحفظ…",
  Retry: "إعادة المحاولة",
  "Nothing to show yet.": "لا يوجد ما يُعرض بعد.",
  "Something went wrong. Please try again.": "حدث خطأ. حاول مرة أخرى.",
  English: "English",
  Doctor: "طبيب",
  Nurse: "تمريض",
  Patient: "مريض",
  "Family caregiver": "مرافق من العائلة",
  // --- dashboards ---
  "Doctor dashboard": "لوحة الطبيب",
  "Nurse dashboard": "لوحة التمريض",
  "My dialysis care": "رعاية الغسيل الخاصة بي",
  "Shared with me": "ما تمت مشاركته معي",
  "Pending physician reviews": "مراجعات بانتظار الطبيب",
  "Sessions with a documentation review waiting for you.": "جلسات لها مراجعة توثيق بانتظارك.",
  "No reviews are waiting.": "لا توجد مراجعات بالانتظار.",
  "Assigned patients": "المرضى المسندون إليك",
  "Only patients on your care team are listed.": "تظهر فقط حالات فريق الرعاية الخاص بك.",
  "No patients are assigned to you.": "لا يوجد مرضى مسندون إليك.",
  "Recent nursing activity": "آخر نشاط تمريضي",
  "Latest nursing actions for your patients.": "أحدث الإجراءات التمريضية لمرضاك.",
  "No nursing actions recorded yet.": "لم تُسجَّل إجراءات تمريضية بعد.",
  Notifications: "الإشعارات",
  unread: "غير مقروءة",
  "No notifications.": "لا توجد إشعارات.",
  "Mark all read": "تعليم الكل كمقروء",
  Session: "الجلسة",
  Findings: "الملاحظات",
  "AI review": "مراجعة الذكاء الاصطناعي",
  Review: "مراجعة",
  "Record no.": "رقم السجل",
  Name: "الاسم",
  "History and labs": "السجل والتحاليل",
  "Open session": "فتح الجلسة",
  Open: "فتح",
  Date: "التاريخ",
  Status: "الحالة",
  "Documented duration": "المدة الموثَّقة",
  // --- doctor patient page ---
  "Dialysis session history": "سجل جلسات الغسيل",
  "No sessions recorded.": "لا توجد جلسات مسجَّلة.",
  "Laboratory trends": "اتجاهات التحاليل المخبرية",
  "Values are shown exactly as reported by the laboratory, with their units.":
    "تُعرض القيم كما وردت من المختبر تماماً مع وحداتها.",
  "No laboratory reports.": "لا توجد تقارير مخبرية.",
  "Reports not yet released to the patient": "تقارير لم تُتَح للمريض بعد",
  Collected: "تاريخ السحب",
  "Release to patient": "إتاحة للمريض",
  "Dialysis orders": "أوامر الغسيل",
  "A new order becomes the active version; earlier versions are kept.":
    "الأمر الجديد يصبح النسخة الفعّالة وتُحفظ النسخ السابقة.",
  "No dialysis order on file.": "لا يوجد أمر غسيل مسجَّل.",
  "Create new order version": "إنشاء نسخة أمر جديدة",
  "Duration (min)": "المدة (دقيقة)",
  "Target UF (mL)": "السحب المستهدف (مل)",
  "Blood flow (mL/min)": "جريان الدم (مل/دقيقة)",
  Access: "المدخل الوعائي",
  Version: "النسخة",
  "(active)": "(فعّالة)",
  "target UF": "السحب المستهدف",
  "blood flow": "جريان الدم",
  access: "المدخل",
  Analyte: "التحليل",
  "Unit:": "الوحدة:",
  "Laboratory reference range": "المدى المرجعي للمختبر",
  "Released to patient": "متاح للمريض",
  Yes: "نعم",
  No: "لا",
  "No laboratory results available.": "لا توجد نتائج مخبرية.",
  // --- doctor session page ---
  "Session review": "مراجعة الجلسة",
  "AI documentation review": "مراجعة التوثيق بالذكاء الاصطناعي",
  Generated: "أُنشئت",
  "Request reanalysis": "طلب إعادة التحليل",
  "No review has been generated for this session yet.": "لم تُنشأ مراجعة لهذه الجلسة بعد.",
  "Model:": "النموذج:",
  "AI analysis is unavailable for this review": "تحليل الذكاء الاصطناعي غير متاح لهذه المراجعة",
  "The rule-based findings below are still valid, and you can review the session as usual.":
    "نتائج الفحوص الآلية أدناه ما زالت صالحة، ويمكنك مراجعة الجلسة كالمعتاد.",
  "AI-generated.": "مُولَّد بالذكاء الاصطناعي.",
  "Advisory only; requires review by an authorized clinician.": "استشاري فقط ويتطلب مراجعة طبيب مخوَّل.",
  "Documentation gaps": "نواقص التوثيق",
  "synthetic demo policy": "سياسة تجريبية مصطنعة",
  "Questions for you": "أسئلة لك",
  "Rule-based documentation checks": "فحوص التوثيق الآلية",
  "No gaps were found by the automated checks.": "لم تجد الفحوص الآلية أي نواقص.",
  "AI session summary": "ملخص الجلسة بالذكاء الاصطناعي",
  version: "النسخة",
  "Generate new version": "إنشاء نسخة جديدة",
  "No summary yet. One is generated when the session is completed.": "لا يوجد ملخص بعد. يُنشأ عند إكمال الجلسة.",
  "AI summary generation failed or was rejected by validation": "فشل إنشاء الملخص أو رفضه التحقق الآلي",
  "The session record is unaffected.": "سجل الجلسة لم يتأثر.",
  "Documented events": "الأحداث الموثَّقة",
  "Nursing actions": "الإجراءات التمريضية",
  "Missing information": "معلومات ناقصة",
  "None.": "لا يوجد.",
  "Patient-friendly version (shown to the patient only after release)": "نسخة مبسّطة للمريض (تظهر له بعد الإتاحة فقط)",
  "Verify summary": "اعتماد الملخص",
  Reject: "رفض",
  "Nursing actions and observations": "الإجراءات والملاحظات التمريضية",
  "Your feedback": "ملاحظاتك",
  "The nursing team is notified. Feedback cannot be edited after sending.":
    "يُبلَّغ فريق التمريض. لا يمكن تعديل الملاحظة بعد إرسالها.",
  "Send feedback": "إرسال الملاحظة",
  Type: "النوع",
  About: "بخصوص",
  "The whole session": "الجلسة كاملة",
  Feedback: "ملاحظة",
  "Request clarification": "طلب توضيح",
  "No feedback sent for this session.": "لم تُرسل ملاحظات لهذه الجلسة.",
  // --- nurse ---
  "Today's dialysis schedule": "جدول الغسيل لليوم",
  "Open a session to start it and document care.": "افتح جلسة لبدئها وتوثيق الرعاية.",
  "No sessions are scheduled for today.": "لا توجد جلسات مجدولة اليوم.",
  "Schedule a session": "جدولة جلسة",
  "Schedule session": "جدولة الجلسة",
  Start: "وقت البدء",
  "Doctor feedback inbox": "ملاحظات الأطباء",
  "Feedback and clarification requests on your patients' sessions.": "ملاحظات وطلبات توضيح على جلسات مرضاك.",
  "No feedback yet.": "لا توجد ملاحظات بعد.",
  "Dialysis session": "جلسة الغسيل",
  scheduled: "مجدولة",
  "Start session": "بدء الجلسة",
  "Pre-treatment weight (kg)": "الوزن قبل الجلسة (كغم)",
  "Complete the session": "إكمال الجلسة",
  "Complete session": "إكمال الجلسة",
  "Post-treatment weight (kg)": "الوزن بعد الجلسة (كغم)",
  "Ultrafiltration volume (mL)": "حجم السحب (مل)",
  "Document care": "توثيق الرعاية",
  "Signed entries cannot be edited. To correct one, add a new entry that explains the correction.":
    "لا يمكن تعديل الإدخالات الموقَّعة. للتصحيح أضف إدخالاً جديداً يوضّح التصحيح.",
  "Vital sign": "علامة حيوية",
  "Nursing action": "إجراء تمريضي",
  "Machine reading": "قراءة الجهاز",
  "Event / incident": "حدث / حادثة",
  Note: "ملاحظة",
  Measurement: "القياس",
  When: "التوقيت",
  "Before treatment": "قبل الجلسة",
  "During treatment": "أثناء الجلسة",
  "After treatment": "بعد الجلسة",
  Value: "القيمة",
  "Enter the value in the unit shown.": "أدخل القيمة بالوحدة المبيَّنة.",
  "Record vital sign": "تسجيل العلامة الحيوية",
  Action: "الإجراء",
  "What was done": "ما الذي تم",
  Reason: "السبب",
  "An action without a reason is flagged as incomplete.": "الإجراء بلا سبب يُعلَّم كتوثيق ناقص.",
  "Record nursing action": "تسجيل الإجراء التمريضي",
  Reading: "القراءة",
  "Typed from the machine display. The system does not connect to the machine.":
    "تُكتب من شاشة الجهاز. النظام لا يتصل بالجهاز.",
  "Record machine reading": "تسجيل قراءة الجهاز",
  "What happened": "ما الذي حدث",
  "Record event": "تسجيل الحدث",
  "Nursing note": "ملاحظة تمريضية",
  "Add note": "إضافة ملاحظة",
  "Documentation completeness": "اكتمال التوثيق",
  "Automated checks on what is recorded. They do not judge clinical decisions.":
    "فحوص آلية لما تم تسجيله. لا تحكم على القرارات السريرية.",
  "Checks run after the first nursing action is recorded.": "تُجرى الفحوص بعد تسجيل أول إجراء تمريضي.",
  "No documentation gaps found": "لا توجد نواقص في التوثيق",
  "Doctor feedback on this session": "ملاحظات الطبيب على هذه الجلسة",
  "No feedback on this session.": "لا توجد ملاحظات على هذه الجلسة.",
  "Nursing action timeline": "التسلسل الزمني للإجراءات التمريضية",
  "Document resolution": "توثيق المعالجة",
  Resolution: "المعالجة",
  "No nursing documentation yet.": "لا يوجد توثيق تمريضي بعد.",
  Event: "حدث",
  "(amendment)": "(تصحيح)",
  "Reason:": "السبب:",
  "No reason documented": "لم يُوثَّق سبب",
  "Resolved:": "المعالجة:",
  "No resolution documented": "لم تُوثَّق معالجة",
  // --- measurements ---
  Source: "المصدر",
  "Prescribed duration": "المدة الموصوفة",
  "Pre-treatment weight": "الوزن قبل الجلسة",
  "Post-treatment weight": "الوزن بعد الجلسة",
  "Ultrafiltration volume": "حجم السحب",
  "Not recorded": "غير مسجَّل",
  prescribed: "موصوف",
  calculated: "محسوب",
  measured: "مقاس",
  // --- patient ---
  "Treatment summaries": "ملخصات الجلسات",
  "Each summary was reviewed and released by a doctor. Discuss any question with your care team.":
    "كل ملخص راجعه طبيب وأتاحه. ناقش أي سؤال مع فريقك الطبي.",
  "No summaries have been released yet.": "لم تُتَح ملخصات بعد.",
  "No summaries are shared with you.": "لا توجد ملخصات مشاركة معك.",
  "Session of": "جلسة",
  released: "أُتيح في",
  "Upcoming sessions": "الجلسات القادمة",
  "No upcoming sessions to show.": "لا توجد جلسات قادمة.",
  "Completed sessions": "الجلسات المكتملة",
  "Sessions per week, then the most recent ones.": "عدد الجلسات أسبوعياً ثم أحدثها.",
  "Shown only if the patient has shared this with you.": "تظهر فقط إذا شاركها المريض معك.",
  "No completed sessions to show.": "لا توجد جلسات مكتملة.",
  "Completed dialysis sessions per week": "جلسات الغسيل المكتملة أسبوعياً",
  "Laboratory results": "النتائج المخبرية",
  "Only results a doctor has released are shown.": "تظهر فقط النتائج التي أتاحها الطبيب.",
  "No laboratory results to show.": "لا توجد نتائج مخبرية.",
  "Family sharing": "المشاركة مع العائلة",
  "You decide what a family caregiver can see. You can stop sharing at any time.":
    "أنت تحدّد ما يراه المرافق. يمكنك إيقاف المشاركة في أي وقت.",
  "You are not sharing with anyone.": "لا تشارك مع أحد حالياً.",
  "Stop sharing": "إيقاف المشاركة",
  Stopped: "أُوقفت في",
  "Share with caregiver": "مشاركة مع مرافق",
  "Caregiver username": "اسم مستخدم المرافق",
  "What to share": "ما الذي تشاركه",
  "Reviewed summaries": "الملخصات المعتمدة",
  "Summaries and appointments": "الملخصات والمواعيد",
  "Summaries, appointments and released lab results": "الملخصات والمواعيد والتحاليل المتاحة",
  "Home measurements": "قياسات منزلية",
  "Measurements you enter are marked as patient-reported for your care team.":
    "القياسات التي تدخلها تُعلَّم لفريقك الطبي بأنها من المريض.",
  "Submit measurement": "إرسال القياس",
  "You have not submitted any measurements.": "لم ترسل أي قياسات.",
  // --- statuses and codes (humanized by format.label) ---
  Scheduled: "مجدولة",
  "In progress": "جارية",
  Completed: "مكتملة",
  Cancelled: "ملغاة",
  "Pending review": "بانتظار المراجعة",
  Unverified: "غير معتمد",
  Verified: "معتمد",
  Rejected: "مرفوض",
  Reviewed: "تمت المراجعة",
  Released: "متاح للمريض",
  "Not released": "غير متاح للمريض",
  "Ai unavailable": "الذكاء الاصطناعي غير متاح",
  Processing: "قيد المعالجة",
  "Clarification request": "طلب توضيح",
  "Systolic bp": "الضغط الانقباضي",
  "Diastolic bp": "الضغط الانبساطي",
  "Heart rate": "النبض",
  Temperature: "الحرارة",
  Spo2: "تشبّع الأكسجين",
  Weight: "الوزن",
  "Blood flow rate": "معدل جريان الدم",
  "Dialysate flow rate": "معدل جريان المحلول",
  "Venous pressure": "الضغط الوريدي",
  "Arterial pressure": "الضغط الشرياني",
  "Uf rate": "معدل السحب",
  "Uf removed": "السحب المنجز",
  "Access care": "العناية بالمدخل الوعائي",
  "Uf adjustment": "تعديل السحب",
  "Treatment pause": "إيقاف مؤقت للعلاج",
  "Fluid bolus": "إعطاء سوائل",
  "Position change": "تغيير الوضعية",
  "Physician notified": "إبلاغ الطبيب",
  "Medication administration": "إعطاء دواء",
  Other: "أخرى",
  Symptom: "عرَض",
  Hypotension: "هبوط الضغط",
  Cramps: "تشنجات",
  Clotting: "تخثر",
  "Machine alarm": "إنذار الجهاز",
  "Access issue": "مشكلة في المدخل الوعائي",
  Incident: "حادثة",
  Measured: "مقاس",
  Device: "من الجهاز",
  "Patient reported": "من المريض",
  Calculated: "محسوب",
  pre: "قبل",
  intra: "أثناء",
  post: "بعد",
  home: "منزلي",
  Summaries: "الملخصات",
  Appointments: "المواعيد",
  Labs: "التحاليل",
  "Required field missing": "حقل مطلوب ناقص",
  "Duration differs from prescription": "المدة تختلف عن الموصوفة",
  "Action without reason": "إجراء بلا سبب",
  "Follow up missing": "متابعة ناقصة",
  "Conflicting records": "سجلات متعارضة",
  "Event without resolution": "حدث بلا معالجة",
  "Protocol reference unavailable": "لا يوجد مرجع بروتوكول",
  // --- notification titles sent by the server ---
  "New nursing action documented": "وُثِّق إجراء تمريضي جديد",
  "Documentation review is ready": "مراجعة التوثيق جاهزة",
  "A doctor left feedback on a session": "ترك الطبيب ملاحظة على جلسة",
  "A session summary is available": "ملخص جلسة متاح",
  // --- validation messages ---
  "Username is required.": "اسم المستخدم مطلوب.",
  "Password is required.": "كلمة المرور مطلوبة.",
  "Feedback is required.": "الملاحظة مطلوبة.",
  "Description is required.": "الوصف مطلوب.",
  "Note is required.": "الملاحظة مطلوبة.",
  "Resolution is required.": "المعالجة مطلوبة.",
  "Caregiver username is required.": "اسم مستخدم المرافق مطلوب.",
  "Enter a number.": "أدخل رقماً.",
  "Choose a patient.": "اختر مريضاً.",
  "Choose a date and time.": "اختر التاريخ والوقت.",
  "At least 30 minutes.": "٣٠ دقيقة على الأقل.",
  "At most 600 minutes.": "٦٠٠ دقيقة على الأكثر.",
};

let current: Locale = "ar";
const listeners = new Set<() => void>();

export function getLocale(): Locale {
  return current;
}

export function setLocale(locale: Locale, persist = true) {
  current = locale;
  if (typeof document !== "undefined") {
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
    if (persist) {
      try {
        window.localStorage.setItem(STORAGE_KEY, locale); // a per-viewer preference, nothing sensitive
      } catch {
        /* storage unavailable: the choice simply lasts for this page view */
      }
    }
  }
  listeners.forEach((notify) => notify());
}

/** Translate a source string for the current locale. */
export function tr(text: string): string {
  return current === "ar" ? (AR[text] ?? text) : text;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Re-renders the calling component when the language changes. */
export function useLocale(): Locale {
  return useSyncExternalStore(subscribe, getLocale, () => "ar" as Locale);
}

/** Translated text node: <Tx k="Sign in" /> */
export function Tx({ k }: { k: string }) {
  useLocale();
  return <>{tr(k)}</>;
}

/** Applies the saved language choice after hydration (server render is always Arabic, RTL). */
export function LocaleBoot() {
  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = window.localStorage.getItem(STORAGE_KEY);
    } catch {
      saved = null;
    }
    setLocale(saved === "en" ? "en" : "ar", false);
  }, []);
  return null;
}
