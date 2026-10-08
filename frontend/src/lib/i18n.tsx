"use client";

import { useEffect, useSyncExternalStore } from "react";
import { AR_EXTRA, arabicRules } from "./arabic";
import { AR_CATALOG } from "./arabic-catalog";

/**
 * Arabic-first interface. Source strings are English; `tr()` returns the Arabic text when the
 * locale is "ar" (the default) and the source string otherwise. A string with no entry falls back
 * to its source. System templates and bundled demo content also have Arabic counterparts.
 * Unrecognized free text remains the original record; localization never rewrites stored data.
 */
export type Locale = "ar" | "en";
const STORAGE_KEY = "kulya.locale";

const BASE_AR: Record<string, string> = {
  // --- shell, auth ---
  "Kulya": "كُلية",
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
  Sections: "الأقسام",
  "Physician workspace": "مساحة عمل الطبيب",
  "Nursing workspace": "مساحة عمل التمريض",
  "Patient companion": "رفيق المريض",
  "Family access": "وصول العائلة",
  "Reviews waiting": "مراجعات بالانتظار",
  "Need your review": "بحاجة إلى مراجعتك",
  "Findings to review": "ملاحظات للمراجعة",
  "Across open reviews": "ضمن المراجعات المفتوحة",
  "On your care team": "ضمن فريق رعايتك",
  "Recent nursing actions": "إجراءات تمريضية حديثة",
  "Latest entries": "أحدث الإدخالات",
  "Sessions today": "جلسات اليوم",
  "Scheduled for today": "مجدولة لهذا اليوم",
  "In progress now": "جارية الآن",
  "Sessions currently running": "جلسات قيد التنفيذ",
  "Doctor feedback": "ملاحظات الأطباء",
  "Messages from doctors": "رسائل من الأطباء",
  "Next session": "الجلسة القادمة",
  "No session scheduled": "لا توجد جلسة مجدولة",
  "Released summaries": "ملخصات متاحة",
  "Reviewed and released by a doctor": "راجعها الطبيب وأتاحها",
  "Released lab reports": "تقارير مخبرية متاحة",
  "Released by a doctor": "أتاحها الطبيب",
  "Doctor reviewed": "راجعه الطبيب",
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
  // --- nutrition ---
  "Renal dietitian": "أخصائي تغذية كلوية",
  "Nutrition workspace": "مساحة عمل التغذية",
  "Nutrition": "التغذية",
  "Nutrition log": "تسجيل الوجبات",
  "Energy": "الطاقة",
  "Protein": "البروتين",
  "Sodium": "الصوديوم",
  "Potassium": "البوتاسيوم",
  "Phosphorus": "الفوسفور",
  "Calcium": "الكالسيوم",
  "Fluid": "السوائل",
  "grams": "غرام",
  "millilitres": "مليلتر",
  "serving": "حصة",
  "piece": "قطعة",
  "cup": "كوب",
  "glass": "قدح",
  "tablespoon": "ملعقة طعام",
  "Not available": "غير متوفر",
  "Estimates only, from a demonstration food list that has not been verified. This is not medical advice: ask your care team before changing what you eat.": "قيم تقديرية فقط من قائمة أطعمة تجريبية لم يتم التحقق منها. هذه ليست نصيحة طبية: استشر فريق رعايتك قبل تغيير طعامك.",
  "Daily average on days with complete records.": "المعدل اليومي في الأيام المكتملة التسجيل.",
  "Meals recorded on": "سُجّلت وجبات في",
  "of": "من",
  "days": "يوماً",
  "meals": "وجبة",
  "day(s) have no meal record. They are unknown, not days without eating.": "يوم/أيام بلا تسجيل للوجبات. هي أيام غير معروفة وليست أياماً بلا طعام.",
  "No nutrition plan has been approved by your care team yet.": "لم يعتمد فريق رعايتك خطة تغذية بعد.",
  "approved by": "اعتمدها",
  "up to": "حتى",
  "per meal": "لكل وجبة",
  "Allergies": "الحساسية",
  "Meals today": "وجبات اليوم",
  "Days recorded": "أيام مسجَّلة",
  "In the last 7 days": "في آخر ٧ أيام",
  "Nutrition plan": "خطة التغذية",
  "Approved": "معتمدة",
  "None yet": "لا توجد بعد",
  "Set by your care team": "وضعها فريق رعايتك",
  "Ideas stay general until one is approved": "تبقى الأفكار عامة إلى أن تُعتمد خطة",
  "Today": "اليوم",
  "Totals of the meals recorded today.": "مجموع الوجبات المسجَّلة اليوم.",
  "Add a meal": "إضافة وجبة",
  "No meal recorded today.": "لم تُسجَّل وجبة اليوم.",
  "Last 7 days": "آخر ٧ أيام",
  "Written and approved by a doctor or dietitian. The app never changes it.": "كتبها واعتمدها طبيب أو أخصائي تغذية. التطبيق لا يغيّرها أبداً.",
  "Meal diary": "سجل الوجبات",
  "The last 30 days, newest first.": "آخر ٣٠ يوماً، الأحدث أولاً.",
  "No meals recorded in this period.": "لا توجد وجبات مسجَّلة في هذه الفترة.",
  "Recorded by": "سجّلها",
  "Remove": "إزالة",
  "not in the food list": "غير موجود في قائمة الأطعمة",
  "Breakfast": "فطور",
  "Lunch": "غداء",
  "Dinner": "عشاء",
  "Snack": "وجبة خفيفة",
  "Confirmed": "مؤكَّدة",
  "Needs review": "تحتاج مراجعة",
  "Pending": "بانتظار المراجعة",
  "Draft": "مسودة",
  "Compatible": "ضمن حدود الخطة",
  "Check portion": "راجع الكمية",
  "Needs dietitian review": "تحتاج مراجعة أخصائي التغذية",
  "General": "عامة",
  "Eating difficulty": "صعوبة في الأكل",
  "Nausea": "غثيان",
  "Loss of appetite": "فقدان الشهية",
  "The assistant is unavailable right now. Add the foods yourself below.": "المساعد غير متاح الآن. أضف الأطعمة بنفسك أدناه.",
  "Add at least one food, each with an amount above zero.": "أضف طعاماً واحداً على الأقل، ولكلٍّ كمية أكبر من صفر.",
  "Meal saved": "تم حفظ الوجبة",
  "Some foods or portions are not confirmed, so some values are not available.": "بعض الأطعمة أو الكميات غير مؤكَّدة، لذلك بعض القيم غير متوفرة.",
  "Add another meal": "إضافة وجبة أخرى",
  "Open the diary": "فتح سجل الوجبات",
  "1. Describe the meal": "١. صف الوجبة",
  "Type it, say it, or take a photo. The assistant only suggests: you check every line before anything is saved.": "اكتبها أو قلها أو التقط صورة. المساعد يقترح فقط: أنت تراجع كل سطر قبل حفظ أي شيء.",
  "What did you eat?": "ماذا أكلت؟",
  "For example: 2 boiled eggs, 1 piece bread, 1 glass tea": "مثال: بيضتان مسلوقتان، قطعة خبز، قدح شاي",
  "Listening…": "جارٍ الاستماع…",
  "Speak": "تحدّث",
  "Photo attached": "تم إرفاق الصورة",
  "Take or choose a photo": "التقط أو اختر صورة",
  "Looking…": "جارٍ البحث…",
  "Find foods": "ابحث عن الأطعمة",
  "Add a food myself": "أضف طعاماً بنفسي",
  "The photo is used once to suggest foods and is not stored. Speaking uses your browser's own speech service.": "تُستخدم الصورة مرة واحدة لاقتراح الأطعمة ولا تُخزَّن. التحدّث يستخدم خدمة الكلام الخاصة بمتصفحك.",
  "2. Check and save": "٢. راجع واحفظ",
  "Correct the food and amount on each line, then tick it when it is right.": "صحّح الطعام والكمية في كل سطر، ثم ضع علامة عندما يكون صحيحاً.",
  "Food": "الطعام",
  "What it was": "ما هو",
  "Food in the list": "الطعام في القائمة",
  "Not in the list (values unknown)": "غير موجود في القائمة (القيم غير معروفة)",
  "Amount": "الكمية",
  "Unit": "الوحدة",
  "This food and amount are right": "هذا الطعام وهذه الكمية صحيحان",
  "about": "حوالي",
  "The assistant was not sure. Please check.": "المساعد لم يكن متأكداً. يرجى المراجعة.",
  "Meal": "الوجبة",
  "Save meal": "حفظ الوجبة",
  "Portion sizes are estimates. Please check each one.": "الكميات تقديرية. يرجى مراجعة كل واحدة.",
  "The offline demo provider cannot read photos. Type or say what was eaten.": "المزوّد التجريبي غير المتصل لا يستطيع قراءة الصور. اكتب أو قل ما تم أكله.",
  "Meal ideas": "أفكار للوجبات",
  "Recipes are compared with the approved plan by fixed rules. A personalized idea is shown to the patient only after a doctor or dietitian approves it.": "تُقارَن الوصفات بالخطة المعتمدة وفق قواعد ثابتة. لا تُعرض الفكرة المخصَّصة على المريض إلا بعد اعتماد طبيب أو أخصائي تغذية.",
  "Look for meal ideas": "ابحث عن أفكار للوجبات",
  "No meal ideas to show yet.": "لا توجد أفكار وجبات بعد.",
  "Compared with the approved plan": "مقارَنة بالخطة المعتمدة",
  "General idea, not personalized": "فكرة عامة، غير مخصَّصة",
  "How to prepare": "طريقة التحضير",
  "Approve": "اعتماد",
  "No approved nutrition plan: this is a general idea, not personalized.": "لا توجد خطة تغذية معتمدة: هذه فكرة عامة وغير مخصَّصة.",
  "Within every per-meal limit set in the approved plan.": "ضمن كل حدود الوجبة المحددة في الخطة المعتمدة.",
  "Nutrient values are estimates from an unverified demo food catalogue.": "القيم الغذائية تقديرية من قائمة أطعمة تجريبية لم يتم التحقق منها.",
  "This is not a diet order. Ask your care team first.": "هذا ليس أمراً غذائياً. اسأل فريق رعايتك أولاً.",
  "The AI explanation was unavailable; the reasons shown are rule-based.": "شرح الذكاء الاصطناعي غير متاح؛ الأسباب المعروضة مبنية على القواعد.",
  "Food records and laboratory results are shown together. This does not show that any food changed any result.": "تُعرض سجلات الطعام ونتائج المختبر معاً. هذا لا يدل على أن أي طعام غيّر أي نتيجة.",
  "Fewer than half of the days have a meal record, so averages may not reflect usual eating.": "أقل من نصف الأيام فيها تسجيل وجبات، لذلك قد لا تعكس المعدلات الأكل المعتاد.",
  "Food records are self-reported and nutrient values are estimates.": "سجلات الطعام يدخلها المريض بنفسه والقيم الغذائية تقديرية.",
  "No laboratory results to show for this period.": "لا توجد نتائج مخبرية لعرضها في هذه الفترة.",
  "laboratory range": "المدى المخبري",
  "Reviewed by a clinician": "راجعه مختص",
  "Unverified draft. It describes records side by side and does not show that food changed any result.": "مسودة غير موثَّقة. تصف السجلات جنباً إلى جنب ولا تدل على أن الطعام غيّر أي نتيجة.",
  "The AI draft was unavailable or rejected by the safety checks. The recorded facts are still shown.": "مسودة الذكاء الاصطناعي غير متاحة أو رفضتها فحوص السلامة. الحقائق المسجَّلة ما زالت معروضة.",
  "Clinician note": "ملاحظة المختص",
  "Approve for the patient": "اعتماد للمريض",
  "Reject draft": "رفض المسودة",
  "Food diary and laboratory results": "سجل الطعام ونتائج المختبر",
  "The last 30 days, shown side by side. Many things other than food affect laboratory results.": "آخر ٣٠ يوماً، جنباً إلى جنب. عوامل كثيرة غير الطعام تؤثر في نتائج المختبر.",
  "Food and laboratory review": "مراجعة الطعام والمختبر",
  "A descriptive draft for the clinician. It never states a cause.": "مسودة وصفية للمختص. لا تذكر سبباً أبداً.",
  "Draft a review": "إعداد مسودة مراجعة",
  "No review has been shared yet.": "لم تُشارَك أي مراجعة بعد.",
  "Print or save as PDF": "طباعة أو حفظ PDF",
  "Recorded facts": "الحقائق المسجَّلة",
  "Dialysis sessions in this period": "جلسات الغسيل في هذه الفترة",
  "Narrative": "النص الوصفي",
  "AI-drafted, reviewed and released by": "صاغه الذكاء الاصطناعي، وراجعه وأتاحه",
  "Unverified draft. Not visible to the patient until a clinician releases this report.": "مسودة غير موثَّقة. لا يراها المريض حتى يتيح مختص هذا التقرير.",
  "No AI narrative: it was unavailable or rejected by the safety checks.": "لا يوجد نص من الذكاء الاصطناعي: لم يكن متاحاً أو رفضته فحوص السلامة.",
  "Release to the patient": "إتاحة للمريض",
  "Nutrition reports": "تقارير التغذية",
  "Facts are calculated from the records. The narrative is an AI draft that a doctor or dietitian reviews before release.": "تُحسب الحقائق من السجلات. النص الوصفي مسودة ذكاء اصطناعي يراجعها طبيب أو أخصائي تغذية قبل الإتاحة.",
  "Draft a report for the last 30 days": "إعداد مسودة تقرير لآخر ٣٠ يوماً",
  "No report has been drafted yet.": "لم تُعدّ أي مسودة تقرير بعد.",
  "No report has been released yet.": "لم يُتَح أي تقرير بعد.",
  "Only a doctor or dietitian approves a plan. Saving creates a new version; earlier versions are kept.": "لا يعتمد الخطة إلا طبيب أو أخصائي تغذية. الحفظ ينشئ نسخة جديدة وتبقى النسخ السابقة محفوظة.",
  "No nutrition plan has been approved yet.": "لم تُعتمد خطة تغذية بعد.",
  "Versions on file": "النسخ المحفوظة",
  "Approve new plan version": "اعتماد نسخة جديدة من الخطة",
  "Potassium limit per meal (mg)": "حد البوتاسيوم لكل وجبة (ملغ)",
  "Sodium limit per meal (mg)": "حد الصوديوم لكل وجبة (ملغ)",
  "Phosphorus limit per meal (mg)": "حد الفوسفور لكل وجبة (ملغ)",
  "Fluid limit per meal (mL)": "حد السوائل لكل وجبة (مل)",
  "Allergies (comma separated)": "الحساسية (افصل بفواصل)",
  "Recipes containing these are never suggested.": "الوصفات التي تحتوي عليها لا تُقترح أبداً.",
  "Guidance for the patient": "إرشادات للمريض",
  "Nursing observations about eating": "ملاحظات التمريض عن الأكل",
  "A nurse records what the patient reports and can refer it to the doctor and dietitian.": "يسجّل التمريض ما يذكره المريض ويمكنه إحالته إلى الطبيب وأخصائي التغذية.",
  "No observations recorded.": "لا توجد ملاحظات مسجَّلة.",
  "Referred": "مُحالة",
  "Record observation": "تسجيل ملاحظة",
  "Observation": "الملاحظة",
  "Refer to doctor and dietitian": "إحالة إلى الطبيب وأخصائي التغذية",
  "What was observed or reported": "ما لوحظ أو ذُكر",
  "Observation is required.": "الملاحظة مطلوبة.",
  "Nutrition overview": "نظرة عامة على التغذية",
  "Food and lab results": "الطعام ونتائج المختبر",
  "No patient has shared their nutrition information with you.": "لم يشارك أي مريض معلومات تغذيته معك.",
  "The patient has not allowed you to record meals for them.": "لم يسمح لك المريض بتسجيل الوجبات نيابةً عنه.",
  "Diary and plan": "السجل والخطة",
  "Dietitian dashboard": "لوحة أخصائي التغذية",
  "Meal ideas to review": "أفكار وجبات للمراجعة",
  "Report drafts": "مسودات التقارير",
  "Not yet released": "لم تُتَح بعد",
  "Nurse referrals": "إحالات التمريض",
  "Open a patient to review the diary, approve a plan, and review AI drafts.": "افتح مريضاً لمراجعة السجل واعتماد خطة ومراجعة مسودات الذكاء الاصطناعي.",
  "Open nutrition review": "فتح مراجعة التغذية",
  "All of the above and my food diary": "كل ما سبق مع سجل طعامي",
  "All of the above, and they may record meals for me": "كل ما سبق، ويمكنه تسجيل الوجبات نيابةً عني",
  "Meal suggestions await review": "أفكار وجبات بانتظار المراجعة",
  "A nutrition report is available": "تقرير تغذية متاح",
  "A nurse referred a nutrition concern": "أحال التمريض ملاحظة عن التغذية",
};

const AR = { ...BASE_AR, ...AR_EXTRA, ...AR_CATALOG };
const rules = arabicRules(text => translateArabic(text));

function translateArabic(text: string, depth = 0): string {
  if (Object.hasOwn(AR, text)) return AR[text];
  if (depth > 8 || !/[a-z]/i.test(text)) return text;
  const normalized = text.replaceAll("_", " ").replace(/^./, c => c.toUpperCase());
  if (Object.hasOwn(AR, normalized)) return AR[normalized];
  for (const [pattern, render] of rules) {
    const match = text.match(pattern);
    if (match) return render(...match.slice(1));
  }
  if (text.includes(" · ")) return text.split(" · ").map(part => translateArabic(part, depth + 1)).join(" · ");
  // Keep complete field-error templates together before splitting narrative sentences.
  const colon = text.indexOf(": ");
  if (colon > 0) {
    const prefix = text.slice(0, colon);
    const translated = translateArabic(prefix, depth + 1);
    if (translated !== prefix) return `${translated}: ${translateArabic(text.slice(colon + 2), depth + 1)}`;
  }
  // Generated narratives are composed of independently translated system sentences.
  const sentences = text.split(/(?<=[.!?])\s+(?=[A-Za-z0-9])/);
  if (sentences.length > 1) return sentences.map(sentence => translateArabic(sentence, depth + 1)).join(" ");
  const parenthetical = text.match(/^(.+) \(([^()]+)\)$/);
  if (parenthetical) {
    const prefix = translateArabic(parenthetical[1], depth + 1);
    if (prefix !== parenthetical[1]) return `${prefix} (${translateArabic(parenthetical[2], depth + 1)})`;
  }
  return text;
}

/** Used by coverage checks so new UI copy cannot silently fall back to English. */
export function hasArabicTranslation(text: string): boolean {
  return !/[a-z]/i.test(text) || translateArabic(text) !== text;
}

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
    document.title = locale === "ar" ? "كُلية" : "Kulya";
    const description = document.querySelector('meta[name="description"]');
    description?.setAttribute("content", tr("Dialysis documentation review and session summaries. Synthetic demonstration data only."));
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
  return current === "ar" ? translateArabic(text) : text;
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
