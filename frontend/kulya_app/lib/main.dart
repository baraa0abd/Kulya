import 'package:flutter/material.dart';

import 'api.dart';
import 'dashboard.dart';
import 'l10n/app_localizations.dart';
import 'login.dart';
import 'state.dart';
import 'summaries.dart';
import 'widgets.dart';

void main() => runApp(KulyaApp(state: AppState(Api())));

class KulyaApp extends StatelessWidget {
  const KulyaApp({super.key, required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    onGenerateTitle: (context) => context.t.appTitle,
    // Arabic first: the locale is fixed to ar, which also makes the whole app right-to-left.
    locale: const Locale('ar'),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales,
    theme: kulyaTheme,
    // One screen per role, chosen by sign-in state. A patient never gets the clinical dashboard.
    home: ListenableBuilder(
      listenable: state,
      builder: (context, _) => switch (state.role) {
        null => LoginScreen(state),
        'patient' => PatientScreen(state),
        _ => DashboardScreen(state),
      },
    ),
  );
}
