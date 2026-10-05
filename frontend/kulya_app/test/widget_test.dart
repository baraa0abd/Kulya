import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kulya_app/api.dart';
import 'package:kulya_app/drafts.dart';
import 'package:kulya_app/l10n/app_localizations.dart';
import 'package:kulya_app/logic.dart';
import 'package:kulya_app/main.dart';
import 'package:kulya_app/session_form.dart';
import 'package:kulya_app/state.dart';
import 'package:kulya_app/summaries.dart';

/// Fails the test if the app touches the network.
class _NoNetwork extends Interceptor {
  int calls = 0;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    calls++;
    handler.reject(DioException(requestOptions: options, message: 'network blocked in tests'));
  }
}

(AppState, _NoNetwork) offlineState() {
  final guard = _NoNetwork();
  final dio = Dio(BaseOptions(baseUrl: 'http://test.invalid'))..interceptors.add(guard);
  return (AppState(Api(dio: dio)), guard);
}

Widget host(Widget child) => MaterialApp(
  locale: const Locale('ar'),
  localizationsDelegates: AppLocalizations.localizationsDelegates,
  supportedLocales: AppLocalizations.supportedLocales,
  home: Scaffold(body: child),
);

void main() {
  group('logic', () {
    test('F-T5 parses Arabic-Indic, Persian and Latin digits', () {
      expect(parseNumber('١٤٠'), 140);
      expect(parseNumber('۱۴۰'), 140);
      expect(parseNumber(' 140 '), 140);
      expect(parseNumber('٦٢٫٩'), 62.9);
      expect(parseNumber(''), isNull);
      expect(parseNumber('abc'), isNull);
    });

    test('typo-guard ranges', () {
      expect(checkVital('pre_sbp', '1200'), VitalError.outOfRange);
      expect(checkVital('pre_sbp', '١٤٠'), isNull);
      expect(checkVital('pre_sbp', ''), isNull);
      expect(checkVital('pre_weight_kg', 'x'), VitalError.invalidNumber);
    });

    test('dates and times', () {
      expect(isIsoDate('2026-10-01'), isTrue);
      expect(isIsoDate('1/10/2026'), isFalse);
      expect(isClockTime('08:00'), isTrue);
      expect(isClockTime('25:00'), isFalse);
    });

    test('highlight ranges tolerate diacritics, tatweel and alef forms', () {
      const note = 'حسّت ببرد ورجفة بنص الجلسة، وأُغمي عليها';
      final ranges = highlightRanges(note, ['ببرد ورجفة', 'اغمي عليها', 'غير موجود']);
      expect(ranges.length, 2);
      expect(note.substring(ranges[0].$1, ranges[0].$2), 'ببرد ورجفة');
      expect(note.substring(ranges[1].$1, ranges[1].$2), 'أُغمي عليها');
    });

    test('patients only ever see approved patient-audience summaries', () {
      final shown = visibleToPatient([
        {'id': 1, 'status': 'approved', 'audience': 'patient'},
        {'id': 2, 'status': 'draft', 'audience': 'patient'},
        {'id': 3, 'status': 'approved', 'audience': 'clinician'},
        {'id': 4, 'status': 'invalid', 'audience': 'patient'},
      ]);
      expect(shown.map((s) => s['id']), [1]);
    });
  });

  testWidgets('F-T1 app starts in Arabic, right-to-left, on the login screen', (tester) async {
    await tester.pumpWidget(KulyaApp(state: offlineState().$1));
    await tester.pumpAndSettle();
    expect(find.text('تسجيل الدخول'), findsOneWidget);
    expect(Directionality.of(tester.element(find.text('تسجيل الدخول'))), TextDirection.rtl);
  });

  testWidgets('F-T7/F-T8 draft shows highlights and the mentioned-values warning', (tester) async {
    final (state, _) = offlineState();
    final draft = {
      'id': 5,
      'note': 9,
      'session': 3,
      'status': 'pending',
      'note_text_ar': 'حسّت ببرد ورجفة والضغط صار ٩٥ على ٦٠ وقفنا السحب',
      'validation_errors': <dynamic>[],
      'payload': {
        'symptoms': [
          {'code': 'chills', 'label_ar': 'برد ورجفة', 'timing': 'intra', 'evidence_span': 'ببرد ورجفة'},
        ],
        'access_findings': <dynamic>[],
        'staff_actions': [
          {'description_ar': 'إيقاف السحب', 'evidence_span': 'وقفنا السحب'},
        ],
        'mentioned_values': [
          {'kind': 'bp', 'raw_text': '٩٥ على ٦٠'},
        ],
        'missing_info': <dynamic>[],
        'uncertain': <dynamic>[],
      },
    };
    await tester.pumpWidget(host(SingleChildScrollView(child: DraftCard(state, draft))));
    await tester.pumpAndSettle();

    final note = tester.widget<Text>(find.descendant(of: find.byType(HighlightedNote), matching: find.byType(Text)));
    final highlighted = (note.textSpan! as TextSpan).children!.where((s) => s.style?.backgroundColor != null);
    expect(highlighted.length, 3);
    expect(find.text('أرقام مذكورة في الملاحظة — لم تُنقل تلقائياً'), findsOneWidget);
    expect(find.text('اعتماد'), findsOneWidget);
    expect(find.byType(TextField), findsNothing); // no vitals field to prefill anywhere on the card
  });

  testWidgets('F-T9 an invalid draft cannot be approved', (tester) async {
    final (state, _) = offlineState();
    final draft = {
      'id': 6,
      'note': 9,
      'session': 3,
      'status': 'invalid',
      'note_text_ar': 'ملاحظة',
      'payload': <String, dynamic>{},
      'validation_errors': [
        {'code': 'evidence_not_found', 'path': 'symptoms/0', 'message': 'x'},
      ],
    };
    await tester.pumpWidget(host(SingleChildScrollView(child: DraftCard(state, draft))));
    await tester.pumpAndSettle();
    expect(find.text('اعتماد'), findsNothing);
    expect(find.text('إعادة الاستخلاص'), findsOneWidget);
    expect(find.text('رفض'), findsOneWidget);
  });

  testWidgets('F-T6 an out-of-range value blocks submit with no API call', (tester) async {
    tester.view.physicalSize = const Size(900, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final (state, guard) = offlineState();
    state
      ..role = 'nurse'
      ..patients = [
        {'id': 1, 'code': 'SYN-001'},
      ]
      ..patientId = 1;
    await tester.pumpWidget(host(SessionForm(state)));
    await tester.enterText(find.widgetWithText(TextFormField, 'الانقباضي قبل'), '1200');
    await tester.tap(find.text('حفظ الجلسة'));
    await tester.pumpAndSettle();
    expect(find.textContaining('خارج المدى المعقول'), findsOneWidget);
    expect(guard.calls, 0);
  });

  testWidgets('F-T11/F-T12 summary actions by role, and the patient screen', (tester) async {
    final (state, _) = offlineState();
    final draft = {
      'id': 1,
      'patient': 1,
      'audience': 'patient',
      'status': 'draft',
      'period_start': '2026-09-01',
      'period_end': '2026-09-30',
      'validation_errors': <dynamic>[],
      'sentences': [
        {
          'text_ar': 'وُثقت رجفة أثناء الجلسة.',
          'citations': [11, 12],
        },
      ],
    };
    state.role = 'nurse';
    await tester.pumpWidget(host(SingleChildScrollView(child: SummaryCard(state, draft))));
    expect(find.text('اعتماد'), findsNothing);
    expect(find.text('ملاحظة 12'), findsOneWidget);

    state.role = 'doctor';
    await tester.pumpWidget(host(SingleChildScrollView(child: SummaryCard(state, draft, key: UniqueKey()))));
    expect(find.text('اعتماد'), findsOneWidget);

    state
      ..role = 'patient'
      ..username = 'patient_syn001'
      ..mySummaries = [
        {...draft, 'id': 2, 'status': 'approved'},
        draft, // must be filtered out even if the API returned it
      ];
    await tester.pumpWidget(host(PatientScreen(state)));
    expect(find.text('وُثقت رجفة أثناء الجلسة.'), findsOneWidget);
    expect(find.text('ناقش أي سؤال مع فريقك الطبي'), findsOneWidget);
    expect(find.text('اعتماد'), findsNothing);
  });
}
