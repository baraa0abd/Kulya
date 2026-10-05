import 'package:flutter/material.dart';

import 'api.dart';
import 'logic.dart';
import 'state.dart';
import 'widgets.dart';

/// Nurse review of AI extraction drafts: the original note with every evidence span highlighted,
/// next to the extracted items. Nothing here is in the record until "approve".
class DraftsPanel extends StatelessWidget {
  const DraftsPanel(this.state, {super.key});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    if (state.drafts.isEmpty) {
      return Center(
        child: Text(context.t.noDrafts, style: const TextStyle(color: KColors.muted)),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(12),
      itemCount: state.drafts.length,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (context, i) => DraftCard(state, state.drafts[i], key: ValueKey(state.drafts[i]['id'])),
    );
  }
}

const _factLists = ['symptoms', 'access_findings', 'staff_actions'];

class DraftCard extends StatefulWidget {
  const DraftCard(this.state, this.draft, {super.key});

  final AppState state;
  final Json draft;

  @override
  State<DraftCard> createState() => _DraftCardState();
}

class _DraftCardState extends State<DraftCard> {
  // "list:index" of items the nurse removed before approving.
  final _removed = <String>{};
  String? _focusedSpan;

  Json get _payload => (widget.draft['payload'] as Json?) ?? const {};

  List<Json> _items(String list) => ((_payload[list] as List?) ?? const []).cast<Json>();

  /// The full payload minus removed items; null when nothing was removed (approve as-is).
  Json? _editedPayload() {
    if (_removed.isEmpty) return null;
    return {
      for (final key in _payload.keys)
        key: [
          for (final (i, item) in _items(key).indexed)
            if (!_removed.contains('$key:$i')) item,
        ],
    };
  }

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final state = widget.state;
    final draft = widget.draft;
    final id = draft['id'] as int;
    final invalid = draft['status'] == 'invalid';
    final errors = ((draft['validation_errors'] as List?) ?? const []).cast<Json>();
    final mentioned = _items('mentioned_values');
    final uncertain = _items('uncertain');
    final missing = _items('missing_info');

    return Card(
      color: KColors.background,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${t.sessionLabel('${draft['session']}')} · ${t.noteTitle('${draft['note']}')}',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                StatusBadge(draft['status'] as String?),
              ],
            ),
            const SizedBox(height: 4),
            Text(t.aiDraftBadge, style: const TextStyle(fontSize: 12, color: KColors.attention)),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white,
                border: Border.all(color: KColors.line),
                borderRadius: BorderRadius.circular(8),
              ),
              child: HighlightedNote('${draft['note_text_ar']}', evidenceSpans(_payload), focused: _focusedSpan),
            ),
            if (invalid && errors.isNotEmpty) ...[
              const SizedBox(height: 10),
              _Box(
                color: KColors.danger,
                background: KColors.dangerSoft,
                title: t.validationErrors,
                lines: [for (final e in errors) '${e['code']}: ${e['message']}'],
              ),
            ],
            for (final list in _factLists) _factSection(list),
            if (mentioned.isNotEmpty) ...[
              const SizedBox(height: 10),
              _Box(
                color: KColors.attention,
                background: KColors.attentionSoft,
                title: t.mentionedValues,
                lines: [for (final v in mentioned) '${v['raw_text']}'],
              ),
            ],
            if (uncertain.isNotEmpty) ...[
              const SizedBox(height: 10),
              _Box(
                color: KColors.muted,
                background: Colors.white,
                title: t.uncertain,
                lines: [for (final u in uncertain) '«${u['text']}» — ${u['reason_ar']}'],
              ),
            ],
            if (missing.isNotEmpty) ...[
              const SizedBox(height: 10),
              _Box(
                color: KColors.info,
                background: KColors.infoSoft,
                title: t.missingInfo,
                lines: [for (final m in missing) '${m['field']}: ${m['reason_ar']}'],
              ),
            ],
            const SizedBox(height: 12),
            if (!invalid) Text(t.editHint, style: const TextStyle(fontSize: 12, color: KColors.muted)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (!invalid)
                  FilledButton.icon(
                    onPressed: state.busy ? null : () => state.approveDraft(id, _editedPayload()),
                    icon: const Icon(Icons.check),
                    label: Text(_removed.isEmpty ? t.approve : t.approveEdited),
                  ),
                OutlinedButton(onPressed: state.busy ? null : () => state.rejectDraft(id), child: Text(t.reject)),
                OutlinedButton(onPressed: state.busy ? null : () => state.retryDraft(id), child: Text(t.retry)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _factSection(String list) {
    final items = _items(list);
    if (items.isEmpty) return const SizedBox.shrink();
    final t = context.t;
    final title = switch (list) {
      'symptoms' => t.symptoms,
      'access_findings' => t.accessFindings,
      _ => t.staffActions,
    };
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: KColors.muted),
          ),
          const SizedBox(height: 4),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final (i, item) in items.indexed)
                if (!_removed.contains('$list:$i'))
                  InputChip(
                    label: Text('${item['label_ar'] ?? item['description_ar']}'),
                    selected: _focusedSpan == item['evidence_span'],
                    showCheckmark: false,
                    onPressed: () => setState(() => _focusedSpan = item['evidence_span'] as String?),
                    onDeleted: widget.draft['status'] == 'invalid'
                        ? null
                        : () => setState(() => _removed.add('$list:$i')),
                  ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Box extends StatelessWidget {
  const _Box({required this.color, required this.background, required this.title, required this.lines});

  final Color color;
  final Color background;
  final String title;
  final List<String> lines;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(10),
    decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(8)),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 13),
        ),
        for (final line in lines) Text(line, style: const TextStyle(height: 1.5)),
      ],
    ),
  );
}

/// The note text with each evidence span on a highlight; the span of the tapped item is stronger.
class HighlightedNote extends StatelessWidget {
  const HighlightedNote(this.note, this.spans, {super.key, this.focused});

  final String note;
  final List<String> spans;
  final String? focused;

  @override
  Widget build(BuildContext context) {
    final children = <TextSpan>[];
    var cursor = 0;
    for (final (start, end, index) in highlightRanges(note, spans)) {
      if (start > cursor) children.add(TextSpan(text: note.substring(cursor, start)));
      final strong = focused != null && spans[index] == focused;
      children.add(
        TextSpan(
          text: note.substring(start, end),
          style: TextStyle(
            backgroundColor: strong ? KColors.highlightStrong : KColors.highlight,
            fontWeight: strong ? FontWeight.w700 : null,
          ),
        ),
      );
      cursor = end;
    }
    if (cursor < note.length) children.add(TextSpan(text: note.substring(cursor)));
    return Text.rich(TextSpan(children: children), style: const TextStyle(fontSize: 16, height: 1.8));
  }
}
