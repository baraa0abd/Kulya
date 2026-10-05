// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'Kulya';

  @override
  String get appSubtitle => 'Dialysis session review — synthetic data only';

  @override
  String get login => 'Sign in';

  @override
  String get username => 'Username';

  @override
  String get password => 'Password';

  @override
  String get logout => 'Sign out';

  @override
  String get roleNurse => 'Nurse';

  @override
  String get roleDoctor => 'Doctor';

  @override
  String get rolePatient => 'Patient';

  @override
  String get roleAdmin => 'Admin';

  @override
  String get patients => 'Patients';

  @override
  String get selectPatient => 'Select a patient from the list';

  @override
  String get attentionFlags => 'flags';

  @override
  String get bpChart => 'Systolic pressure across sessions';

  @override
  String get preSbp => 'Before session';

  @override
  String get postSbp => 'After session';

  @override
  String get flaggedSession => 'Flagged session';

  @override
  String get sessions => 'Sessions (newest first)';

  @override
  String get originalNote => 'Original note';

  @override
  String get noFactsYet => 'No approved facts yet';

  @override
  String get bpBefore => 'BP before';

  @override
  String get bpLowest => 'Lowest';

  @override
  String get bpAfter => 'BP after';

  @override
  String get weight => 'Weight';

  @override
  String get uf => 'UF';

  @override
  String get drafts => 'Drafts to review';

  @override
  String get newSession => 'New session';

  @override
  String get summaries => 'Summaries';

  @override
  String get noDrafts => 'No drafts waiting for review';

  @override
  String get aiDraftBadge => 'AI draft — not in the record until you approve';

  @override
  String get editHint => 'Remove any wrong item before approving. Tap an item to show its evidence in the text.';

  @override
  String get approve => 'Approve';

  @override
  String get approveEdited => 'Approve with edits';

  @override
  String get reject => 'Reject';

  @override
  String get retry => 'Re-run extraction';

  @override
  String get symptoms => 'Symptoms';

  @override
  String get accessFindings => 'Access findings';

  @override
  String get staffActions => 'Staff actions';

  @override
  String get mentionedValues => 'Numbers mentioned in the note — not copied automatically';

  @override
  String get uncertain => 'Uncertain';

  @override
  String get missingInfo => 'Missing information';

  @override
  String get validationErrors => 'Automatic validation errors';

  @override
  String get statusPending => 'Pending review';

  @override
  String get statusApproved => 'Approved';

  @override
  String get statusRejected => 'Rejected';

  @override
  String get statusInvalid => 'Invalid';

  @override
  String get statusDraft => 'Draft';

  @override
  String get sessionDate => 'Session date (YYYY-MM-DD)';

  @override
  String get startTime => 'Start time (HH:MM)';

  @override
  String get endTime => 'End time (HH:MM)';

  @override
  String get preSbpField => 'Systolic before';

  @override
  String get preDbpField => 'Diastolic before';

  @override
  String get postSbpField => 'Systolic after';

  @override
  String get postDbpField => 'Diastolic after';

  @override
  String get minIntraSbp => 'Lowest systolic during session';

  @override
  String get preWeight => 'Weight before (kg)';

  @override
  String get postWeight => 'Weight after (kg)';

  @override
  String get ufVolume => 'UF volume (ml)';

  @override
  String get accessType => 'Access type';

  @override
  String get note => 'Nursing note (free text)';

  @override
  String get save => 'Save session';

  @override
  String get sessionSaved => 'Session saved.';

  @override
  String noteSavedWithDraft(String status) {
    return 'Note saved. Draft status: $status';
  }

  @override
  String get invalidNumber => 'Not a valid number';

  @override
  String outOfRange(String min, String max) {
    return 'Outside the plausible range ($min–$max)';
  }

  @override
  String get requiredField => 'Required';

  @override
  String get invalidDate => 'Invalid date';

  @override
  String get invalidTime => 'Invalid time';

  @override
  String get endAfterStart => 'End time must be after start time';

  @override
  String get audience => 'Summary for';

  @override
  String get audienceClinician => 'Care team';

  @override
  String get audiencePatient => 'Patient';

  @override
  String get periodStart => 'From (YYYY-MM-DD)';

  @override
  String get periodEnd => 'To (YYYY-MM-DD)';

  @override
  String get requestSummary => 'Request summary';

  @override
  String get noSummaries => 'No summary requested for this patient in this sign-in';

  @override
  String get summariesSessionOnly => 'Only summaries requested since you signed in are listed here.';

  @override
  String get doctorApprovesHint => 'Only a doctor can approve a summary.';

  @override
  String get emptySummary => 'No sentences: there are no approved facts in this period.';

  @override
  String citation(String id) {
    return 'Note $id';
  }

  @override
  String noteTitle(String id) {
    return 'Note $id';
  }

  @override
  String get close => 'Close';

  @override
  String get patientFooter => 'Discuss any question with your care team';

  @override
  String get mySummaries => 'My approved summaries';

  @override
  String get noApprovedSummaries => 'No approved summaries yet';

  @override
  String get genericError => 'Something went wrong. Please try again.';

  @override
  String get adminNoClinical => 'Admin accounts cannot view clinical data.';

  @override
  String sessionLabel(String id) {
    return 'Session $id';
  }

  @override
  String get refresh => 'Refresh';

  @override
  String get syntheticBanner =>
      'All data is synthetic. Thresholds are for demonstration and are not clinical guidance.';
}
