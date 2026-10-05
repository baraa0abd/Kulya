import 'package:flutter/material.dart';

import 'l10n/app_localizations.dart';
import 'state.dart';

extension L10n on BuildContext {
  AppLocalizations get t => AppLocalizations.of(this)!;
}

/// Calm clinical palette: one accent, amber for "attention" flags, blue for "info" flags.
abstract final class KColors {
  static const accent = Color(0xFF0F766E);
  static const accentSoft = Color(0xFFD5F0EC);
  static const background = Color(0xFFF4F7F8);
  static const attention = Color(0xFFB45309);
  static const attentionSoft = Color(0xFFFEF3C7);
  static const info = Color(0xFF1D4ED8);
  static const infoSoft = Color(0xFFDBEAFE);
  static const danger = Color(0xFFB91C1C);
  static const dangerSoft = Color(0xFFFEE2E2);
  static const muted = Color(0xFF5B6B73);
  static const line = Color(0xFFDCE3E6);
  static const highlight = Color(0xFFFDE68A);
  static const highlightStrong = Color(0xFFF59E0B);
}

final kulyaTheme = ThemeData(
  colorScheme: ColorScheme.fromSeed(seedColor: KColors.accent, surface: Colors.white),
  scaffoldBackgroundColor: KColors.background,
  cardTheme: const CardThemeData(
    elevation: 0,
    margin: EdgeInsets.zero,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.all(Radius.circular(12)),
      side: BorderSide(color: KColors.line),
    ),
  ),
  inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder(), isDense: true),
  // Large touch targets for tablet use.
  filledButtonTheme: FilledButtonThemeData(style: FilledButton.styleFrom(minimumSize: const Size(64, 48))),
  outlinedButtonTheme: OutlinedButtonThemeData(style: OutlinedButton.styleFrom(minimumSize: const Size(64, 48))),
);

String statusLabel(BuildContext context, String? status) => switch (status) {
  'pending' => context.t.statusPending,
  'approved' => context.t.statusApproved,
  'rejected' => context.t.statusRejected,
  'invalid' => context.t.statusInvalid,
  'draft' => context.t.statusDraft,
  _ => status ?? '',
};

String roleLabel(BuildContext context, String? role) => switch (role) {
  'nurse' => context.t.roleNurse,
  'doctor' => context.t.roleDoctor,
  'patient' => context.t.rolePatient,
  'admin' => context.t.roleAdmin,
  _ => role ?? '',
};

class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.color = KColors.muted, this.background = KColors.background});

  final String text;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
    decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(999)),
    child: Text(
      text,
      style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600),
    ),
  );
}

class StatusBadge extends StatelessWidget {
  const StatusBadge(this.status, {super.key});

  final String? status;

  @override
  Widget build(BuildContext context) {
    final (color, background) = switch (status) {
      'approved' => (KColors.accent, KColors.accentSoft),
      'rejected' || 'invalid' => (KColors.danger, KColors.dangerSoft),
      _ => (KColors.attention, KColors.attentionSoft),
    };
    return Pill(statusLabel(context, status), color: color, background: background);
  }
}

/// A titled card section.
class Panel extends StatelessWidget {
  const Panel({super.key, required this.title, required this.child, this.trailing});

  final String title;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(child: Text(title, style: Theme.of(context).textTheme.titleMedium)),
              ?trailing,
            ],
          ),
          const SizedBox(height: 10),
          child,
        ],
      ),
    ),
  );
}

/// Shows the backend's Arabic error message (and field details for validation errors).
class ErrorBanner extends StatelessWidget {
  const ErrorBanner(this.state, {super.key});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    final failure = state.failure;
    if (failure == null) return const SizedBox.shrink();
    final details = failure.details;
    final hasDetails = details is Map && details.isNotEmpty;
    return Material(
      color: KColors.dangerSoft,
      child: ListTile(
        dense: true,
        leading: const Icon(Icons.error_outline, color: KColors.danger),
        title: Text(failure.messageAr ?? context.t.genericError, style: const TextStyle(color: KColors.danger)),
        subtitle: hasDetails ? Text('$details', maxLines: 3, overflow: TextOverflow.ellipsis) : null,
        trailing: IconButton(icon: const Icon(Icons.close), tooltip: context.t.close, onPressed: state.clearFailure),
      ),
    );
  }
}

AppBar kulyaAppBar(BuildContext context, AppState state) => AppBar(
  backgroundColor: Colors.white,
  surfaceTintColor: Colors.white,
  title: Row(
    children: [
      Text(
        context.t.appTitle,
        style: const TextStyle(fontWeight: FontWeight.w800, color: KColors.accent),
      ),
      const SizedBox(width: 12),
      Flexible(
        child: Text(
          context.t.appSubtitle,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 14, color: KColors.muted),
        ),
      ),
    ],
  ),
  actions: [
    Center(child: Pill('${state.username} · ${roleLabel(context, state.role)}')),
    if (state.role != 'patient')
      IconButton(
        icon: const Icon(Icons.refresh),
        tooltip: context.t.refresh,
        onPressed: state.busy ? null : state.refresh,
      ),
    TextButton.icon(onPressed: state.logout, icon: const Icon(Icons.logout), label: Text(context.t.logout)),
    const SizedBox(width: 8),
  ],
  bottom: PreferredSize(
    preferredSize: const Size.fromHeight(4),
    child: state.busy ? const LinearProgressIndicator(minHeight: 4) : const SizedBox(height: 4),
  ),
);
