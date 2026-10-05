import 'package:flutter/material.dart';

import 'drafts.dart';
import 'session_form.dart';
import 'state.dart';
import 'summaries.dart';
import 'timeline.dart';
import 'widgets.dart';

/// The single staff screen: patients | chart + timeline | work panel (drafts, new session, summaries).
class DashboardScreen extends StatelessWidget {
  const DashboardScreen(this.state, {super.key});

  final AppState state;

  static const _minWidth = 1180.0;

  @override
  Widget build(BuildContext context) {
    final body = state.isClinician
        ? Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(width: 240, child: PatientList(state)),
                const SizedBox(width: 12),
                Expanded(child: TimelinePanel(state)),
                const SizedBox(width: 12),
                SizedBox(width: 400, child: WorkPanel(state)),
              ],
            ),
          )
        : Center(child: Text(context.t.adminNoClinical));
    return Scaffold(
      appBar: kulyaAppBar(context, state),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            color: KColors.infoSoft,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            child: Text(context.t.syntheticBanner, style: const TextStyle(color: KColors.info, fontSize: 13)),
          ),
          ErrorBanner(state),
          Expanded(
            // Tablet-first: below the tablet width the dashboard scrolls sideways instead of squeezing.
            child: LayoutBuilder(
              builder: (context, box) => box.maxWidth >= _minWidth
                  ? body
                  : SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: SizedBox(width: _minWidth, child: body),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

class PatientList extends StatelessWidget {
  const PatientList(this.state, {super.key});

  final AppState state;

  @override
  Widget build(BuildContext context) => Panel(
    title: context.t.patients,
    child: Expanded(
      child: ListView.separated(
        itemCount: state.patients.length,
        separatorBuilder: (_, _) => const SizedBox(height: 8),
        itemBuilder: (context, i) {
          final p = state.patients[i];
          final selected = p['id'] == state.patientId;
          final flags = p['attention_flag_count'] as int? ?? 0;
          return Material(
            color: selected ? KColors.accentSoft : KColors.background,
            borderRadius: BorderRadius.circular(10),
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: state.busy ? null : () => state.selectPatient(p['id'] as int),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${p['code']}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                    Text('${p['display_name_ar']}', style: const TextStyle(color: KColors.muted)),
                    if (flags > 0) ...[
                      const SizedBox(height: 6),
                      Pill(
                        '$flags ${context.t.attentionFlags}',
                        color: KColors.attention,
                        background: KColors.attentionSoft,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        },
      ),
    ),
  );
}

class WorkPanel extends StatelessWidget {
  const WorkPanel(this.state, {super.key});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    final tabs = <(String, Widget)>[
      if (state.isNurse) ('${context.t.drafts} (${state.drafts.length})', DraftsPanel(state)),
      if (state.isNurse) (context.t.newSession, SessionForm(state, key: ValueKey('form-${state.patientId}'))),
      (context.t.summaries, SummariesPanel(state, key: ValueKey('summaries-${state.patientId}'))),
    ];
    return Card(
      clipBehavior: Clip.antiAlias,
      child: DefaultTabController(
        length: tabs.length,
        child: Column(
          children: [
            TabBar(
              tabs: [for (final (label, _) in tabs) Tab(text: label)],
              labelPadding: const EdgeInsets.symmetric(horizontal: 6),
            ),
            Expanded(child: TabBarView(children: [for (final (_, view) in tabs) view])),
          ],
        ),
      ),
    );
  }
}
