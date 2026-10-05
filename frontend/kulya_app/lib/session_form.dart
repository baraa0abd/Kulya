import 'package:flutter/material.dart';

import 'logic.dart';
import 'state.dart';
import 'widgets.dart';

/// Nurse entry: typed vitals (either digit style) plus a free-text Arabic note.
/// Vitals may be left empty; the rules engine flags what is missing.
class SessionForm extends StatefulWidget {
  const SessionForm(this.state, {super.key});

  final AppState state;

  @override
  State<SessionForm> createState() => _SessionFormState();
}

class _SessionFormState extends State<SessionForm> {
  final _form = GlobalKey<FormState>();
  final _date = TextEditingController(text: DateTime.now().toIso8601String().substring(0, 10));
  final _start = TextEditingController(text: '08:00');
  final _end = TextEditingController(text: '12:00');
  final _note = TextEditingController();
  final _vitals = {for (final field in vitalRanges.keys) field: TextEditingController()};
  String _access = 'AVF';

  @override
  void dispose() {
    for (final c in [_date, _start, _end, _note, ..._vitals.values]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _vitalError(String field, String? input) {
    final (min, max) = vitalRanges[field]!;
    return switch (checkVital(field, input ?? '')) {
      null => null,
      VitalError.invalidNumber => context.t.invalidNumber,
      VitalError.outOfRange => context.t.outOfRange('$min', '$max'),
    };
  }

  Future<void> _submit() async {
    // Invalid input never reaches the API.
    if (!_form.currentState!.validate()) return;
    final t = context.t;
    final messenger = ScaffoldMessenger.of(context);
    final body = <String, dynamic>{
      'session_date': _date.text.trim(),
      'start_time': _start.text.trim(),
      'end_time': _end.text.trim(),
      'access_type': _access,
      for (final MapEntry(key: field, value: controller) in _vitals.entries)
        if (parseNumber(controller.text) case final value?)
          field: field.endsWith('_kg') ? value.toStringAsFixed(1) : value.round(),
    };
    final status = await widget.state.createSession(body, _note.text);
    if (status == null || !mounted) return;
    messenger.showSnackBar(
      SnackBar(content: Text(status.isEmpty ? t.sessionSaved : t.noteSavedWithDraft(statusLabel(context, status)))),
    );
    _note.clear();
    for (final c in _vitals.values) {
      c.clear();
    }
  }

  Widget _number(String field, String label) => Expanded(
    child: TextFormField(
      controller: _vitals[field],
      decoration: InputDecoration(labelText: label),
      textDirection: TextDirection.ltr,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      validator: (v) => _vitalError(field, v),
    ),
  );

  Widget _row(List<Widget> children) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final (i, child) in children.indexed) ...[if (i > 0) const SizedBox(width: 10), child],
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final state = widget.state;
    if (state.patient == null) return Center(child: Text(t.selectPatient));
    return Form(
      key: _form,
      child: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          Text('${state.patient!['code']}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          const SizedBox(height: 12),
          TextFormField(
            controller: _date,
            decoration: InputDecoration(labelText: t.sessionDate),
            textDirection: TextDirection.ltr,
            validator: (v) => isIsoDate((v ?? '').trim()) ? null : t.invalidDate,
          ),
          const SizedBox(height: 12),
          _row([
            Expanded(
              child: TextFormField(
                controller: _start,
                decoration: InputDecoration(labelText: t.startTime),
                textDirection: TextDirection.ltr,
                validator: (v) => isClockTime((v ?? '').trim()) ? null : t.invalidTime,
              ),
            ),
            Expanded(
              child: TextFormField(
                controller: _end,
                decoration: InputDecoration(labelText: t.endTime),
                textDirection: TextDirection.ltr,
                validator: (v) {
                  final end = (v ?? '').trim();
                  if (!isClockTime(end)) return t.invalidTime;
                  return end.compareTo(_start.text.trim()) > 0 ? null : t.endAfterStart;
                },
              ),
            ),
          ]),
          _row([_number('pre_sbp', t.preSbpField), _number('pre_dbp', t.preDbpField)]),
          _row([_number('post_sbp', t.postSbpField), _number('post_dbp', t.postDbpField)]),
          _row([_number('min_intra_sbp', t.minIntraSbp), _number('uf_volume_ml', t.ufVolume)]),
          _row([_number('pre_weight_kg', t.preWeight), _number('post_weight_kg', t.postWeight)]),
          DropdownButtonFormField<String>(
            initialValue: _access,
            decoration: InputDecoration(labelText: t.accessType),
            items: [
              for (final a in const ['AVF', 'AVG', 'CVC']) DropdownMenuItem(value: a, child: Text(a)),
            ],
            onChanged: (v) => setState(() => _access = v ?? _access),
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _note,
            decoration: InputDecoration(labelText: t.note, alignLabelWithHint: true),
            minLines: 4,
            maxLines: 8,
          ),
          const SizedBox(height: 14),
          FilledButton.icon(
            onPressed: state.busy ? null : _submit,
            icon: const Icon(Icons.save_outlined),
            label: Text(t.save),
          ),
        ],
      ),
    );
  }
}
