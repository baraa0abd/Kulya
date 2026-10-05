import 'package:flutter/material.dart';

import 'api.dart';
import 'logic.dart';
import 'state.dart';
import 'widgets.dart';

/// Staff: request a cited summary for the selected patient; a doctor approves or rejects it.
class SummariesPanel extends StatefulWidget {
  const SummariesPanel(this.state, {super.key});

  final AppState state;

  @override
  State<SummariesPanel> createState() => _SummariesPanelState();
}

class _SummariesPanelState extends State<SummariesPanel> {
  late final TextEditingController _from;
  late final TextEditingController _to;
  String _audience = 'clinician';

  @override
  void initState() {
    super.initState();
    // Default period: the whole recorded timeline of this patient.
    final dates = [for (final s in widget.state.timeline) '${s['session_date']}']..sort();
    final today = DateTime.now().toIso8601String().substring(0, 10);
    _from = TextEditingController(text: dates.firstOrNull ?? today);
    _to = TextEditingController(text: dates.lastOrNull ?? today);
  }

  @override
  void dispose() {
    _from.dispose();
    _to.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final state = widget.state;
    if (state.patient == null) return Center(child: Text(t.selectPatient));
    final summaries = state.patientSummaries;
    final datesOk = isIsoDate(_from.text.trim()) && isIsoDate(_to.text.trim());
    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        Text('${state.patient!['code']}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        const SizedBox(height: 10),
        Text(t.audience, style: const TextStyle(color: KColors.muted, fontSize: 13)),
        const SizedBox(height: 6),
        SegmentedButton<String>(
          segments: [
            ButtonSegment(value: 'clinician', label: Text(t.audienceClinician)),
            ButtonSegment(value: 'patient', label: Text(t.audiencePatient)),
          ],
          selected: {_audience},
          onSelectionChanged: (s) => setState(() => _audience = s.first),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: _from,
                textDirection: TextDirection.ltr,
                decoration: InputDecoration(labelText: t.periodStart),
                onChanged: (_) => setState(() {}),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                controller: _to,
                textDirection: TextDirection.ltr,
                decoration: InputDecoration(labelText: t.periodEnd),
                onChanged: (_) => setState(() {}),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: state.busy || !datesOk
              ? null
              : () => state.requestSummary(_audience, _from.text.trim(), _to.text.trim()),
          icon: const Icon(Icons.summarize_outlined),
          label: Text(t.requestSummary),
        ),
        const SizedBox(height: 8),
        Text(t.summariesSessionOnly, style: const TextStyle(fontSize: 12, color: KColors.muted)),
        const SizedBox(height: 12),
        if (summaries.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 24),
            child: Center(
              child: Text(t.noSummaries, style: const TextStyle(color: KColors.muted)),
            ),
          ),
        for (final summary in summaries) ...[SummaryCard(state, summary), const SizedBox(height: 12)],
      ],
    );
  }
}

/// One summary: each sentence followed by its citations. Staff can open a cited note.
class SummaryCard extends StatelessWidget {
  const SummaryCard(this.state, this.summary, {super.key, this.large = false});

  final AppState state;
  final Json summary;
  final bool large;

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final id = summary['id'] as int;
    final sentences = ((summary['sentences'] as List?) ?? const []).cast<Json>();
    final errors = ((summary['validation_errors'] as List?) ?? const []).cast<Json>();
    final forPatient = summary['audience'] == 'patient';
    final isDraft = summary['status'] == 'draft';
    return Card(
      color: large ? Colors.white : KColors.background,
      child: Padding(
        padding: EdgeInsets.all(large ? 20 : 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${summary['period_start']} ← ${summary['period_end']}',
                    textDirection: TextDirection.ltr,
                    textAlign: TextAlign.end,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                if (!large) ...[
                  Pill(forPatient ? t.audiencePatient : t.audienceClinician),
                  const SizedBox(width: 6),
                  StatusBadge(summary['status'] as String?),
                ],
              ],
            ),
            const SizedBox(height: 10),
            if (sentences.isEmpty && errors.isEmpty) Text(t.emptySummary, style: const TextStyle(color: KColors.muted)),
            for (final sentence in sentences)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${sentence['text_ar']}', style: TextStyle(fontSize: large ? 21 : 15, height: 1.7)),
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: [
                        for (final noteId in (sentence['citations'] as List).cast<int>())
                          // Patients cannot open clinical notes, so their citations are labels only.
                          ActionChip(
                            label: Text(t.citation('$noteId'), style: const TextStyle(fontSize: 12)),
                            visualDensity: VisualDensity.compact,
                            onPressed: state.isClinician ? () => showNote(context, state, noteId) : null,
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            for (final e in errors)
              Text('${e['code']}: ${e['message']}', style: const TextStyle(color: KColors.danger, fontSize: 13)),
            if (forPatient && !large) ...[
              const Divider(),
              Text(t.patientFooter, style: const TextStyle(color: KColors.muted, fontSize: 13)),
            ],
            if (isDraft && !large) ...[
              const SizedBox(height: 10),
              if (state.isDoctor)
                Wrap(
                  spacing: 8,
                  children: [
                    FilledButton.icon(
                      onPressed: state.busy ? null : () => state.reviewSummary(id, approve: true),
                      icon: const Icon(Icons.check),
                      label: Text(t.approve),
                    ),
                    OutlinedButton(
                      onPressed: state.busy ? null : () => state.reviewSummary(id, approve: false),
                      child: Text(t.reject),
                    ),
                  ],
                )
              else
                Text(t.doctorApprovesHint, style: const TextStyle(color: KColors.muted, fontSize: 13)),
            ],
          ],
        ),
      ),
    );
  }
}

/// Opens the original note behind a citation.
void showNote(BuildContext context, AppState state, int noteId) {
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (context) => FutureBuilder<Json>(
      future: state.fetchNote(noteId),
      builder: (context, snapshot) => Padding(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(context.t.noteTitle('$noteId'), style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            if (snapshot.hasError)
              Text(context.t.genericError, style: const TextStyle(color: KColors.danger))
            else if (!snapshot.hasData)
              const Center(child: CircularProgressIndicator())
            else
              Text('${snapshot.data!['text_ar']}', style: const TextStyle(fontSize: 18, height: 1.8)),
          ],
        ),
      ),
    ),
  );
}

/// The only screen a patient ever sees: their own doctor-approved summaries, in large text.
class PatientScreen extends StatelessWidget {
  const PatientScreen(this.state, {super.key});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    // Filter again on the client: unapproved text must never render here, whatever the API sent.
    final summaries = visibleToPatient(state.mySummaries);
    return Scaffold(
      appBar: kulyaAppBar(context, state),
      body: Column(
        children: [
          ErrorBanner(state),
          Expanded(
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 760),
                child: ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    Text(t.mySummaries, style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 16),
                    if (summaries.isEmpty)
                      Text(t.noApprovedSummaries, style: const TextStyle(fontSize: 18, color: KColors.muted)),
                    for (final s in summaries) ...[SummaryCard(state, s, large: true), const SizedBox(height: 16)],
                  ],
                ),
              ),
            ),
          ),
          Container(
            width: double.infinity,
            color: KColors.accentSoft,
            padding: const EdgeInsets.all(16),
            child: Text(
              t.patientFooter,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: KColors.accent),
            ),
          ),
        ],
      ),
    );
  }
}
