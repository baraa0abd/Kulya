import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale) : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate = _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates = <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[Locale('ar'), Locale('en')];

  /// No description provided for @appTitle.
  ///
  /// In ar, this message translates to:
  /// **'كُلية'**
  String get appTitle;

  /// No description provided for @appSubtitle.
  ///
  /// In ar, this message translates to:
  /// **'مراجعة جلسات الغسيل الكلوي — بيانات تجريبية فقط'**
  String get appSubtitle;

  /// No description provided for @login.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الدخول'**
  String get login;

  /// No description provided for @username.
  ///
  /// In ar, this message translates to:
  /// **'اسم المستخدم'**
  String get username;

  /// No description provided for @password.
  ///
  /// In ar, this message translates to:
  /// **'كلمة المرور'**
  String get password;

  /// No description provided for @logout.
  ///
  /// In ar, this message translates to:
  /// **'خروج'**
  String get logout;

  /// No description provided for @roleNurse.
  ///
  /// In ar, this message translates to:
  /// **'تمريض'**
  String get roleNurse;

  /// No description provided for @roleDoctor.
  ///
  /// In ar, this message translates to:
  /// **'طبيب'**
  String get roleDoctor;

  /// No description provided for @rolePatient.
  ///
  /// In ar, this message translates to:
  /// **'مريض'**
  String get rolePatient;

  /// No description provided for @roleAdmin.
  ///
  /// In ar, this message translates to:
  /// **'إدارة'**
  String get roleAdmin;

  /// No description provided for @patients.
  ///
  /// In ar, this message translates to:
  /// **'المرضى'**
  String get patients;

  /// No description provided for @selectPatient.
  ///
  /// In ar, this message translates to:
  /// **'اختر مريضاً من القائمة'**
  String get selectPatient;

  /// No description provided for @attentionFlags.
  ///
  /// In ar, this message translates to:
  /// **'تنبيهات'**
  String get attentionFlags;

  /// No description provided for @bpChart.
  ///
  /// In ar, this message translates to:
  /// **'الضغط الانقباضي عبر الجلسات'**
  String get bpChart;

  /// No description provided for @preSbp.
  ///
  /// In ar, this message translates to:
  /// **'قبل الجلسة'**
  String get preSbp;

  /// No description provided for @postSbp.
  ///
  /// In ar, this message translates to:
  /// **'بعد الجلسة'**
  String get postSbp;

  /// No description provided for @flaggedSession.
  ///
  /// In ar, this message translates to:
  /// **'جلسة عليها تنبيه'**
  String get flaggedSession;

  /// No description provided for @sessions.
  ///
  /// In ar, this message translates to:
  /// **'الجلسات (الأحدث أولاً)'**
  String get sessions;

  /// No description provided for @originalNote.
  ///
  /// In ar, this message translates to:
  /// **'الملاحظة الأصلية'**
  String get originalNote;

  /// No description provided for @noFactsYet.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد حقائق معتمدة بعد'**
  String get noFactsYet;

  /// No description provided for @bpBefore.
  ///
  /// In ar, this message translates to:
  /// **'الضغط قبل'**
  String get bpBefore;

  /// No description provided for @bpLowest.
  ///
  /// In ar, this message translates to:
  /// **'أدنى ضغط'**
  String get bpLowest;

  /// No description provided for @bpAfter.
  ///
  /// In ar, this message translates to:
  /// **'الضغط بعد'**
  String get bpAfter;

  /// No description provided for @weight.
  ///
  /// In ar, this message translates to:
  /// **'الوزن'**
  String get weight;

  /// No description provided for @uf.
  ///
  /// In ar, this message translates to:
  /// **'السحب'**
  String get uf;

  /// No description provided for @drafts.
  ///
  /// In ar, this message translates to:
  /// **'مسودات للمراجعة'**
  String get drafts;

  /// No description provided for @newSession.
  ///
  /// In ar, this message translates to:
  /// **'جلسة جديدة'**
  String get newSession;

  /// No description provided for @summaries.
  ///
  /// In ar, this message translates to:
  /// **'الملخصات'**
  String get summaries;

  /// No description provided for @noDrafts.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد مسودات بانتظار المراجعة'**
  String get noDrafts;

  /// No description provided for @aiDraftBadge.
  ///
  /// In ar, this message translates to:
  /// **'مسودة آلية — لا تدخل السجل قبل اعتمادك'**
  String get aiDraftBadge;

  /// No description provided for @editHint.
  ///
  /// In ar, this message translates to:
  /// **'احذف أي عنصر غير صحيح قبل الاعتماد. اضغط على العنصر لإظهار دليله في النص.'**
  String get editHint;

  /// No description provided for @approve.
  ///
  /// In ar, this message translates to:
  /// **'اعتماد'**
  String get approve;

  /// No description provided for @approveEdited.
  ///
  /// In ar, this message translates to:
  /// **'اعتماد بعد التعديل'**
  String get approveEdited;

  /// No description provided for @reject.
  ///
  /// In ar, this message translates to:
  /// **'رفض'**
  String get reject;

  /// No description provided for @retry.
  ///
  /// In ar, this message translates to:
  /// **'إعادة الاستخلاص'**
  String get retry;

  /// No description provided for @symptoms.
  ///
  /// In ar, this message translates to:
  /// **'الأعراض'**
  String get symptoms;

  /// No description provided for @accessFindings.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظات المدخل الوعائي'**
  String get accessFindings;

  /// No description provided for @staffActions.
  ///
  /// In ar, this message translates to:
  /// **'إجراءات الفريق'**
  String get staffActions;

  /// No description provided for @mentionedValues.
  ///
  /// In ar, this message translates to:
  /// **'أرقام مذكورة في الملاحظة — لم تُنقل تلقائياً'**
  String get mentionedValues;

  /// No description provided for @uncertain.
  ///
  /// In ar, this message translates to:
  /// **'غير مؤكد'**
  String get uncertain;

  /// No description provided for @missingInfo.
  ///
  /// In ar, this message translates to:
  /// **'معلومات ناقصة'**
  String get missingInfo;

  /// No description provided for @validationErrors.
  ///
  /// In ar, this message translates to:
  /// **'أخطاء التحقق الآلي'**
  String get validationErrors;

  /// No description provided for @statusPending.
  ///
  /// In ar, this message translates to:
  /// **'بانتظار المراجعة'**
  String get statusPending;

  /// No description provided for @statusApproved.
  ///
  /// In ar, this message translates to:
  /// **'معتمد'**
  String get statusApproved;

  /// No description provided for @statusRejected.
  ///
  /// In ar, this message translates to:
  /// **'مرفوض'**
  String get statusRejected;

  /// No description provided for @statusInvalid.
  ///
  /// In ar, this message translates to:
  /// **'غير صالح'**
  String get statusInvalid;

  /// No description provided for @statusDraft.
  ///
  /// In ar, this message translates to:
  /// **'مسودة'**
  String get statusDraft;

  /// No description provided for @sessionDate.
  ///
  /// In ar, this message translates to:
  /// **'تاريخ الجلسة (سنة-شهر-يوم)'**
  String get sessionDate;

  /// No description provided for @startTime.
  ///
  /// In ar, this message translates to:
  /// **'وقت البدء (س:د)'**
  String get startTime;

  /// No description provided for @endTime.
  ///
  /// In ar, this message translates to:
  /// **'وقت الانتهاء (س:د)'**
  String get endTime;

  /// No description provided for @preSbpField.
  ///
  /// In ar, this message translates to:
  /// **'الانقباضي قبل'**
  String get preSbpField;

  /// No description provided for @preDbpField.
  ///
  /// In ar, this message translates to:
  /// **'الانبساطي قبل'**
  String get preDbpField;

  /// No description provided for @postSbpField.
  ///
  /// In ar, this message translates to:
  /// **'الانقباضي بعد'**
  String get postSbpField;

  /// No description provided for @postDbpField.
  ///
  /// In ar, this message translates to:
  /// **'الانبساطي بعد'**
  String get postDbpField;

  /// No description provided for @minIntraSbp.
  ///
  /// In ar, this message translates to:
  /// **'أدنى انقباضي أثناء الجلسة'**
  String get minIntraSbp;

  /// No description provided for @preWeight.
  ///
  /// In ar, this message translates to:
  /// **'الوزن قبل (كغم)'**
  String get preWeight;

  /// No description provided for @postWeight.
  ///
  /// In ar, this message translates to:
  /// **'الوزن بعد (كغم)'**
  String get postWeight;

  /// No description provided for @ufVolume.
  ///
  /// In ar, this message translates to:
  /// **'حجم السحب (مل)'**
  String get ufVolume;

  /// No description provided for @accessType.
  ///
  /// In ar, this message translates to:
  /// **'نوع المدخل الوعائي'**
  String get accessType;

  /// No description provided for @note.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظة التمريض (نص حر)'**
  String get note;

  /// No description provided for @save.
  ///
  /// In ar, this message translates to:
  /// **'حفظ الجلسة'**
  String get save;

  /// No description provided for @sessionSaved.
  ///
  /// In ar, this message translates to:
  /// **'حُفظت الجلسة.'**
  String get sessionSaved;

  /// No description provided for @noteSavedWithDraft.
  ///
  /// In ar, this message translates to:
  /// **'حُفظت الملاحظة. حالة المسودة: {status}'**
  String noteSavedWithDraft(String status);

  /// No description provided for @invalidNumber.
  ///
  /// In ar, this message translates to:
  /// **'رقم غير صحيح'**
  String get invalidNumber;

  /// No description provided for @outOfRange.
  ///
  /// In ar, this message translates to:
  /// **'خارج المدى المعقول ({min}–{max})'**
  String outOfRange(String min, String max);

  /// No description provided for @requiredField.
  ///
  /// In ar, this message translates to:
  /// **'حقل مطلوب'**
  String get requiredField;

  /// No description provided for @invalidDate.
  ///
  /// In ar, this message translates to:
  /// **'تاريخ غير صحيح'**
  String get invalidDate;

  /// No description provided for @invalidTime.
  ///
  /// In ar, this message translates to:
  /// **'وقت غير صحيح'**
  String get invalidTime;

  /// No description provided for @endAfterStart.
  ///
  /// In ar, this message translates to:
  /// **'وقت الانتهاء يجب أن يكون بعد وقت البدء'**
  String get endAfterStart;

  /// No description provided for @audience.
  ///
  /// In ar, this message translates to:
  /// **'الملخص موجَّه إلى'**
  String get audience;

  /// No description provided for @audienceClinician.
  ///
  /// In ar, this message translates to:
  /// **'الفريق الطبي'**
  String get audienceClinician;

  /// No description provided for @audiencePatient.
  ///
  /// In ar, this message translates to:
  /// **'المريض'**
  String get audiencePatient;

  /// No description provided for @periodStart.
  ///
  /// In ar, this message translates to:
  /// **'من (سنة-شهر-يوم)'**
  String get periodStart;

  /// No description provided for @periodEnd.
  ///
  /// In ar, this message translates to:
  /// **'إلى (سنة-شهر-يوم)'**
  String get periodEnd;

  /// No description provided for @requestSummary.
  ///
  /// In ar, this message translates to:
  /// **'طلب ملخص'**
  String get requestSummary;

  /// No description provided for @noSummaries.
  ///
  /// In ar, this message translates to:
  /// **'لم يُطلب أي ملخص لهذا المريض في هذه الجلسة'**
  String get noSummaries;

  /// No description provided for @summariesSessionOnly.
  ///
  /// In ar, this message translates to:
  /// **'تظهر هنا الملخصات التي طُلبت منذ تسجيل دخولك فقط.'**
  String get summariesSessionOnly;

  /// No description provided for @doctorApprovesHint.
  ///
  /// In ar, this message translates to:
  /// **'اعتماد الملخص من صلاحية الطبيب.'**
  String get doctorApprovesHint;

  /// No description provided for @emptySummary.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد جمل: لا توجد حقائق معتمدة في هذه الفترة.'**
  String get emptySummary;

  /// No description provided for @citation.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظة {id}'**
  String citation(String id);

  /// No description provided for @noteTitle.
  ///
  /// In ar, this message translates to:
  /// **'الملاحظة رقم {id}'**
  String noteTitle(String id);

  /// No description provided for @close.
  ///
  /// In ar, this message translates to:
  /// **'إغلاق'**
  String get close;

  /// No description provided for @patientFooter.
  ///
  /// In ar, this message translates to:
  /// **'ناقش أي سؤال مع فريقك الطبي'**
  String get patientFooter;

  /// No description provided for @mySummaries.
  ///
  /// In ar, this message translates to:
  /// **'ملخصاتي المعتمدة'**
  String get mySummaries;

  /// No description provided for @noApprovedSummaries.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد ملخصات معتمدة بعد'**
  String get noApprovedSummaries;

  /// No description provided for @genericError.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ. حاول مرة أخرى.'**
  String get genericError;

  /// No description provided for @adminNoClinical.
  ///
  /// In ar, this message translates to:
  /// **'حساب الإدارة لا يملك صلاحية عرض البيانات السريرية.'**
  String get adminNoClinical;

  /// No description provided for @sessionLabel.
  ///
  /// In ar, this message translates to:
  /// **'جلسة {id}'**
  String sessionLabel(String id);

  /// No description provided for @refresh.
  ///
  /// In ar, this message translates to:
  /// **'تحديث'**
  String get refresh;

  /// No description provided for @syntheticBanner.
  ///
  /// In ar, this message translates to:
  /// **'جميع البيانات تجريبية مصطنعة. العتبات للعرض فقط وليست إرشاداً سريرياً.'**
  String get syntheticBanner;
}

class _AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) => <String>['ar', 'en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
