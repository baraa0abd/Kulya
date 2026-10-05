import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import 'api.dart';
import 'state.dart';
import 'widgets.dart';

const _preColor = KColors.accent;
const _postColor = Color(0xFF64748B);

bool _hasAttention(Json session) => (session['flags'] as List).any((f) => f['severity'] == 'attention');

/// Centre column: patient header, SBP chart, then session cards newest first.
class TimelinePanel extends StatelessWidget {
  const TimelinePanel(this.state, {super.key});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    final patient = state.patient;
    if (patient == null) return Card(child: Center(child: Text(context.t.selectPatient)));
    final sessions = state.timeline;
    return ListView.separated(
      itemCount: sessions.length + 2,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (context, i) {
        if (i == 0) {
          return Panel(
            title: '${patient['code']} — ${patient['display_name_ar']}',
            trailing: Text(context.t.bpChart, style: const TextStyle(color: KColors.muted)),
            child: Column(
              children: [
                SizedBox(height: 190, child: BpChart(sessions)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 16,
                  children: [
                    _Legend(_preColor, context.t.preSbp),
                    _Legend(_postColor, context.t.postSbp),
                    _Legend(KColors.highlightStrong, context.t.flaggedSession),
                  ],
                ),
              ],
            ),
          );
        }
        if (i == 1) {
          return Padding(
            padding: const EdgeInsets.only(top: 4, right: 4, left: 4),
            child: Text(context.t.sessions, style: Theme.of(context).textTheme.titleMedium),
          );
        }
        return SessionCard(sessions[i - 2]);
      },
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend(this.color, this.label);

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: 10,
        height: 10,
        decoration: BoxDecoration(color: color, shape: BoxShape.circle),
      ),
      const SizedBox(width: 6),
      Text(label, style: const TextStyle(fontSize: 13, color: KColors.muted)),
    ],
  );
}

/// Pre/post systolic pressure, oldest to newest. Values are plotted exactly as typed; which
/// sessions are "flagged" comes from the backend rules engine, never from this widget.
class BpChart extends StatelessWidget {
  const BpChart(this.sessionsNewestFirst, {super.key});

  final List<Json> sessionsNewestFirst;

  @override
  Widget build(BuildContext context) {
    final sessions = sessionsNewestFirst.reversed.toList();
    LineChartBarData series(String field, Color color) => LineChartBarData(
      spots: [
        for (var i = 0; i < sessions.length; i++)
          if (sessions[i][field] != null) FlSpot(i.toDouble(), (sessions[i][field] as num).toDouble()),
      ],
      color: color,
      barWidth: 2,
      dotData: FlDotData(
        getDotPainter: (spot, _, _, _) {
          final flagged = _hasAttention(sessions[spot.x.toInt()]);
          return FlDotCirclePainter(
            radius: flagged ? 6 : 3,
            color: flagged ? KColors.highlightStrong : color,
            strokeWidth: flagged ? 2 : 0,
            strokeColor: Colors.white,
          );
        },
      ),
    );
    // Axis bounds snapped to tens so the labels are round numbers (presentation only).
    final values = [
      for (final s in sessions)
        for (final f in const ['pre_sbp', 'post_sbp'])
          if (s[f] != null) (s[f] as num).toDouble(),
    ];
    final low = values.isEmpty ? 0.0 : (values.reduce((a, b) => a < b ? a : b) / 10).floor() * 10.0;
    final high = values.isEmpty ? 10.0 : (values.reduce((a, b) => a > b ? a : b) / 10).ceil() * 10.0;
    const hidden = AxisTitles(sideTitles: SideTitles(showTitles: false));
    // The chart itself reads left-to-right in time, independent of the page direction.
    return Directionality(
      textDirection: TextDirection.ltr,
      child: LineChart(
        LineChartData(
          minY: low,
          maxY: high == low ? low + 10 : high,
          lineBarsData: [series('pre_sbp', _preColor), series('post_sbp', _postColor)],
          gridData: const FlGridData(drawVerticalLine: false),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            topTitles: hidden,
            rightTitles: hidden,
            leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 36)),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                interval: 2,
                reservedSize: 24,
                getTitlesWidget: (value, _) {
                  final i = value.toInt();
                  if (value != i || i < 0 || i >= sessions.length) return const SizedBox.shrink();
                  final date = '${sessions[i]['session_date']}';
                  return Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(date.substring(5), style: const TextStyle(fontSize: 11, color: KColors.muted)),
                  );
                },
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class SessionCard extends StatelessWidget {
  const SessionCard(this.session, {super.key});

  final Json session;

  String _v(String field) => session[field] == null ? '—' : '${session[field]}';

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final facts = session['facts'] as Json?;
    final flags = (session['flags'] as List).cast<Json>();
    final notes = (session['notes'] as List).cast<Json>();
    final time = '${'${session['start_time']}'.substring(0, 5)}–${'${session['end_time']}'.substring(0, 5)}';
    final chips = <Widget>[
      if (facts != null) ...[
        for (final s in facts['symptoms'] as List)
          Pill('${s['label_ar']}', color: KColors.accent, background: KColors.accentSoft),
        for (final a in facts['access_findings'] as List)
          Pill('${a['label_ar']}', color: KColors.danger, background: KColors.dangerSoft),
        for (final a in facts['staff_actions'] as List) Pill('${a['description_ar']}'),
      ],
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('${session['session_date']}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const SizedBox(width: 10),
                Text('$time · ${session['access_type']}', style: const TextStyle(color: KColors.muted)),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${t.bpBefore} ${_v('pre_sbp')}/${_v('pre_dbp')}  ·  ${t.bpLowest} ${_v('min_intra_sbp')}  ·  '
              '${t.bpAfter} ${_v('post_sbp')}/${_v('post_dbp')}  ·  '
              '${t.weight} ${_v('pre_weight_kg')} ← ${_v('post_weight_kg')}  ·  ${t.uf} ${_v('uf_volume_ml')}',
            ),
            for (final flag in flags) ...[const SizedBox(height: 8), FlagRow(flag)],
            const SizedBox(height: 8),
            if (facts == null)
              Text(t.noFactsYet, style: const TextStyle(color: KColors.muted, fontSize: 13))
            else
              Wrap(spacing: 6, runSpacing: 6, children: chips),
            if (notes.isNotEmpty)
              Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: const EdgeInsets.only(bottom: 10),
                  expandedCrossAxisAlignment: CrossAxisAlignment.start,
                  title: Text(
                    '${t.originalNote} (${notes.length})',
                    style: const TextStyle(fontSize: 14, color: KColors.muted),
                  ),
                  children: [
                    for (final note in notes)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('#${note['id']}  ${note['text_ar']}', style: const TextStyle(height: 1.6)),
                      ),
                  ],
                ),
              )
            else
              const SizedBox(height: 10),
          ],
        ),
      ),
    );
  }
}

/// A rule flag: the backend's Arabic message plus the evidence values that triggered it.
class FlagRow extends StatelessWidget {
  const FlagRow(this.flag, {super.key});

  final Json flag;

  @override
  Widget build(BuildContext context) {
    final attention = flag['severity'] == 'attention';
    final evidence = (flag['evidence'] as Json?) ?? const {};
    final shown = {
      for (final e in evidence.entries)
        if (e.value is num || e.value is String) e.key: e.value,
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: attention ? KColors.attentionSoft : KColors.infoSoft,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            attention ? Icons.warning_amber_rounded : Icons.info_outline,
            size: 20,
            color: attention ? KColors.attention : KColors.info,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${flag['message_ar']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                if (shown.isNotEmpty)
                  Directionality(
                    textDirection: TextDirection.ltr,
                    child: Text(
                      '${flag['rule_id']}  ${shown.entries.map((e) => '${e.key}=${e.value}').join('  ')}',
                      style: const TextStyle(fontSize: 12, color: KColors.muted),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
