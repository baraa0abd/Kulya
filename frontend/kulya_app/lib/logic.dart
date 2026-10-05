/// Pure helpers: number parsing, typo-guard ranges, evidence highlighting, patient-side filtering.
/// No flags or thresholds are computed here; those come from the backend rules engine.
library;

const _arabicIndic = '٠١٢٣٤٥٦٧٨٩';
const _persian = '۰۱۲۳۴۵۶۷۸۹';

/// Accepts Latin, Arabic-Indic and Persian digits, and '٫' or ',' as the decimal mark.
/// Returns null for empty or non-numeric input.
num? parseNumber(String input) {
  final buffer = StringBuffer();
  for (final ch in input.trim().split('')) {
    final a = _arabicIndic.indexOf(ch);
    final p = _persian.indexOf(ch);
    if (a >= 0) {
      buffer.write(a);
    } else if (p >= 0) {
      buffer.write(p);
    } else if (ch == '٫' || ch == ',') {
      buffer.write('.');
    } else {
      buffer.write(ch);
    }
  }
  return num.tryParse(buffer.toString());
}

/// Plausible physical ranges mirrored from the backend. Typo guards, NOT clinical thresholds.
const Map<String, (num, num)> vitalRanges = {
  'pre_sbp': (50, 260),
  'post_sbp': (50, 260),
  'min_intra_sbp': (50, 260),
  'pre_dbp': (30, 160),
  'post_dbp': (30, 160),
  'pre_weight_kg': (20, 250),
  'post_weight_kg': (20, 250),
  'uf_volume_ml': (0, 8000),
};

enum VitalError { invalidNumber, outOfRange }

/// Empty input is allowed (the backend flags missing fields). Returns null when acceptable.
VitalError? checkVital(String field, String input) {
  if (input.trim().isEmpty) return null;
  final value = parseNumber(input);
  if (value == null) return VitalError.invalidNumber;
  final (min, max) = vitalRanges[field]!;
  return (value < min || value > max) ? VitalError.outOfRange : null;
}

final _date = RegExp(r'^\d{4}-\d{2}-\d{2}$');
final _time = RegExp(r'^([01]\d|2[0-3]):[0-5]\d$');

bool isIsoDate(String s) => _date.hasMatch(s) && DateTime.tryParse(s) != null;
bool isClockTime(String s) => _time.hasMatch(s);

bool _dropped(int rune) => rune == 0x0640 || (rune >= 0x064B && rune <= 0x0652);

String _fold(String ch) => switch (ch) {
  'أ' || 'إ' || 'آ' => 'ا',
  'ى' => 'ي',
  _ => ch,
};

/// Folded text plus, for each folded character, its index in the original string.
(String, List<int>) _normalizeWithMap(String text) {
  final out = StringBuffer();
  final map = <int>[];
  for (var i = 0; i < text.length; i++) {
    if (_dropped(text.codeUnitAt(i))) continue;
    out.write(_fold(text[i]));
    map.add(i);
  }
  return (out.toString(), map);
}

/// Where each evidence span sits in the raw note, tolerant of tatweel, diacritics and alef forms
/// (the same differences the backend's normalize_ar ignores). Spans that cannot be found are skipped.
/// Result: sorted, non-overlapping (start, end, spanIndex) with end exclusive.
List<(int, int, int)> highlightRanges(String note, List<String> spans) {
  final (folded, map) = _normalizeWithMap(note);
  final found = <(int, int, int)>[];
  for (var s = 0; s < spans.length; s++) {
    final needle = _normalizeWithMap(spans[s].trim()).$1;
    if (needle.isEmpty) continue;
    final at = folded.indexOf(needle);
    if (at < 0) continue;
    found.add((map[at], map[at + needle.length - 1] + 1, s));
  }
  found.sort((a, b) => a.$1.compareTo(b.$1));
  final result = <(int, int, int)>[];
  for (final range in found) {
    if (result.isEmpty || range.$1 >= result.last.$2) result.add(range);
  }
  return result;
}

/// Defence in depth: even if the API returned something else, a patient only ever sees
/// approved, patient-audience summaries.
List<Map<String, dynamic>> visibleToPatient(Iterable<dynamic> summaries) => [
  for (final s in summaries)
    if (s is Map<String, dynamic> && s['status'] == 'approved' && s['audience'] == 'patient') s,
];

/// All verbatim texts of an extraction payload, in a stable order, for highlighting.
List<String> evidenceSpans(Map<String, dynamic> payload) => [
  for (final (list, field) in const [
    ('symptoms', 'evidence_span'),
    ('access_findings', 'evidence_span'),
    ('staff_actions', 'evidence_span'),
    ('mentioned_values', 'raw_text'),
    ('uncertain', 'text'),
  ])
    for (final item in (payload[list] as List? ?? const []))
      if (item is Map && item[field] is String) item[field] as String,
];
