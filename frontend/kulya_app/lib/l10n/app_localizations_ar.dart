// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appTitle => 'كُلية';

  @override
  String get appSubtitle => 'مراجعة جلسات الغسيل الكلوي — بيانات تجريبية فقط';

  @override
  String get login => 'تسجيل الدخول';

  @override
  String get username => 'اسم المستخدم';

  @override
  String get password => 'كلمة المرور';

  @override
  String get logout => 'خروج';

  @override
  String get roleNurse => 'تمريض';

  @override
  String get roleDoctor => 'طبيب';

  @override
  String get rolePatient => 'مريض';

  @override
  String get roleAdmin => 'إدارة';

  @override
  String get patients => 'المرضى';

  @override
  String get selectPatient => 'اختر مريضاً من القائمة';

  @override
  String get attentionFlags => 'تنبيهات';

  @override
  String get bpChart => 'الضغط الانقباضي عبر الجلسات';

  @override
  String get preSbp => 'قبل الجلسة';

  @override
  String get postSbp => 'بعد الجلسة';

  @override
  String get flaggedSession => 'جلسة عليها تنبيه';

  @override
  String get sessions => 'الجلسات (الأحدث أولاً)';

  @override
  String get originalNote => 'الملاحظة الأصلية';

  @override
  String get noFactsYet => 'لا توجد حقائق معتمدة بعد';

  @override
  String get bpBefore => 'الضغط قبل';

  @override
  String get bpLowest => 'أدنى ضغط';

  @override
  String get bpAfter => 'الضغط بعد';

  @override
  String get weight => 'الوزن';

  @override
  String get uf => 'السحب';

  @override
  String get drafts => 'مسودات للمراجعة';

  @override
  String get newSession => 'جلسة جديدة';

  @override
  String get summaries => 'الملخصات';

  @override
  String get noDrafts => 'لا توجد مسودات بانتظار المراجعة';

  @override
  String get aiDraftBadge => 'مسودة آلية — لا تدخل السجل قبل اعتمادك';

  @override
  String get editHint => 'احذف أي عنصر غير صحيح قبل الاعتماد. اضغط على العنصر لإظهار دليله في النص.';

  @override
  String get approve => 'اعتماد';

  @override
  String get approveEdited => 'اعتماد بعد التعديل';

  @override
  String get reject => 'رفض';

  @override
  String get retry => 'إعادة الاستخلاص';

  @override
  String get symptoms => 'الأعراض';

  @override
  String get accessFindings => 'ملاحظات المدخل الوعائي';

  @override
  String get staffActions => 'إجراءات الفريق';

  @override
  String get mentionedValues => 'أرقام مذكورة في الملاحظة — لم تُنقل تلقائياً';

  @override
  String get uncertain => 'غير مؤكد';

  @override
  String get missingInfo => 'معلومات ناقصة';

  @override
  String get validationErrors => 'أخطاء التحقق الآلي';

  @override
  String get statusPending => 'بانتظار المراجعة';

  @override
  String get statusApproved => 'معتمد';

  @override
  String get statusRejected => 'مرفوض';

  @override
  String get statusInvalid => 'غير صالح';

  @override
  String get statusDraft => 'مسودة';

  @override
  String get sessionDate => 'تاريخ الجلسة (سنة-شهر-يوم)';

  @override
  String get startTime => 'وقت البدء (س:د)';

  @override
  String get endTime => 'وقت الانتهاء (س:د)';

  @override
  String get preSbpField => 'الانقباضي قبل';

  @override
  String get preDbpField => 'الانبساطي قبل';

  @override
  String get postSbpField => 'الانقباضي بعد';

  @override
  String get postDbpField => 'الانبساطي بعد';

  @override
  String get minIntraSbp => 'أدنى انقباضي أثناء الجلسة';

  @override
  String get preWeight => 'الوزن قبل (كغم)';

  @override
  String get postWeight => 'الوزن بعد (كغم)';

  @override
  String get ufVolume => 'حجم السحب (مل)';

  @override
  String get accessType => 'نوع المدخل الوعائي';

  @override
  String get note => 'ملاحظة التمريض (نص حر)';

  @override
  String get save => 'حفظ الجلسة';

  @override
  String get sessionSaved => 'حُفظت الجلسة.';

  @override
  String noteSavedWithDraft(String status) {
    return 'حُفظت الملاحظة. حالة المسودة: $status';
  }

  @override
  String get invalidNumber => 'رقم غير صحيح';

  @override
  String outOfRange(String min, String max) {
    return 'خارج المدى المعقول ($min–$max)';
  }

  @override
  String get requiredField => 'حقل مطلوب';

  @override
  String get invalidDate => 'تاريخ غير صحيح';

  @override
  String get invalidTime => 'وقت غير صحيح';

  @override
  String get endAfterStart => 'وقت الانتهاء يجب أن يكون بعد وقت البدء';

  @override
  String get audience => 'الملخص موجَّه إلى';

  @override
  String get audienceClinician => 'الفريق الطبي';

  @override
  String get audiencePatient => 'المريض';

  @override
  String get periodStart => 'من (سنة-شهر-يوم)';

  @override
  String get periodEnd => 'إلى (سنة-شهر-يوم)';

  @override
  String get requestSummary => 'طلب ملخص';

  @override
  String get noSummaries => 'لم يُطلب أي ملخص لهذا المريض في هذه الجلسة';

  @override
  String get summariesSessionOnly => 'تظهر هنا الملخصات التي طُلبت منذ تسجيل دخولك فقط.';

  @override
  String get doctorApprovesHint => 'اعتماد الملخص من صلاحية الطبيب.';

  @override
  String get emptySummary => 'لا توجد جمل: لا توجد حقائق معتمدة في هذه الفترة.';

  @override
  String citation(String id) {
    return 'ملاحظة $id';
  }

  @override
  String noteTitle(String id) {
    return 'الملاحظة رقم $id';
  }

  @override
  String get close => 'إغلاق';

  @override
  String get patientFooter => 'ناقش أي سؤال مع فريقك الطبي';

  @override
  String get mySummaries => 'ملخصاتي المعتمدة';

  @override
  String get noApprovedSummaries => 'لا توجد ملخصات معتمدة بعد';

  @override
  String get genericError => 'حدث خطأ. حاول مرة أخرى.';

  @override
  String get adminNoClinical => 'حساب الإدارة لا يملك صلاحية عرض البيانات السريرية.';

  @override
  String sessionLabel(String id) {
    return 'جلسة $id';
  }

  @override
  String get refresh => 'تحديث';

  @override
  String get syntheticBanner => 'جميع البيانات تجريبية مصطنعة. العتبات للعرض فقط وليست إرشاداً سريرياً.';
}
