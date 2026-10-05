import 'package:flutter/foundation.dart';

import 'api.dart';
import 'logic.dart';

/// All dashboard state in one place. Widgets rebuild through ListenableBuilder.
/// ponytail: one ChangeNotifier instead of a provider graph; split it if panels need independent loading.
class AppState extends ChangeNotifier {
  AppState(this.api);

  final Api api;

  String? username;
  String? role;
  List<Json> patients = [];
  int? patientId;
  List<Json> timeline = [];
  List<Json> drafts = [];
  // Summaries requested since sign-in, newest first (the API has no list endpoint for staff).
  List<Json> summaries = [];
  List<Json> mySummaries = [];
  bool busy = false;
  ApiFailure? failure;

  bool get signedIn => role != null;
  bool get isNurse => role == 'nurse';
  bool get isDoctor => role == 'doctor';
  bool get isClinician => isNurse || isDoctor;
  Json? get patient => patients.where((p) => p['id'] == patientId).firstOrNull;
  List<Json> get patientSummaries => [
    for (final s in summaries)
      if (s['patient'] == patientId) s,
  ];

  /// Runs an API action, tracking busy/error state. Returns false when it failed.
  Future<bool> _run(Future<void> Function() action) async {
    busy = true;
    failure = null;
    notifyListeners();
    try {
      await action();
      return true;
    } catch (error) {
      failure = ApiFailure.from(error);
      return false;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  void clearFailure() {
    failure = null;
    notifyListeners();
  }

  Future<bool> login(String user, String password) => _run(() async {
    final data = await api.login(user, password);
    username = user;
    role = data['role'] as String;
    await _loadForRole();
  });

  void logout() {
    api.logout();
    username = role = null;
    patientId = null;
    patients = timeline = drafts = summaries = mySummaries = [];
    failure = null;
    notifyListeners();
  }

  Future<void> _loadForRole() async {
    if (role == 'patient') {
      mySummaries = visibleToPatient(await api.list('/me/summaries/'));
    } else if (isClinician) {
      patients = await api.list('/patients/');
      if (isNurse) await _loadDrafts();
      patientId ??= patients.firstOrNull?['id'] as int?;
      if (patientId != null) timeline = await api.list('/patients/$patientId/timeline/');
    }
  }

  Future<void> _loadDrafts() async {
    drafts = [
      ...await api.list('/extraction-drafts/?status=pending'),
      ...await api.list('/extraction-drafts/?status=invalid'),
    ];
  }

  Future<bool> refresh() => _run(_loadForRole);

  Future<bool> selectPatient(int id) => _run(() async {
    patientId = id;
    timeline = await api.list('/patients/$id/timeline/');
  });

  /// [edited] is the full extraction payload when the nurse removed items; null approves as-is.
  Future<bool> approveDraft(int id, Json? edited) => _run(() async {
    await api.post('/extraction-drafts/$id/approve/', edited == null ? null : {'edited_payload': edited});
    await _loadForRole();
  });

  Future<bool> rejectDraft(int id) => _run(() async {
    await api.post('/extraction-drafts/$id/reject/');
    await _loadForRole();
  });

  Future<bool> retryDraft(int id) => _run(() async {
    await api.post('/extraction-drafts/$id/retry/');
    await _loadForRole();
  });

  /// Creates the session and, when [note] is not empty, its note. Returns the draft status of the
  /// note (or '' when there was no note), or null when the request failed.
  Future<String?> createSession(Json vitals, String note) async {
    var status = '';
    final ok = await _run(() async {
      final session = await api.post('/patients/$patientId/sessions/', vitals);
      if (note.trim().isNotEmpty) {
        final created = await api.post('/sessions/${session['id']}/notes/', {'text_ar': note.trim()});
        status = created['draft_status'] as String? ?? '';
      }
      await _loadForRole();
    });
    return ok ? status : null;
  }

  Future<bool> requestSummary(String audience, String start, String end) => _run(() async {
    final summary = await api.post('/patients/$patientId/summaries/', {
      'audience': audience,
      'period_start': start,
      'period_end': end,
    });
    summaries = [summary, ...summaries];
  });

  Future<bool> reviewSummary(int id, {required bool approve}) => _run(() async {
    final updated = await api.post('/summaries/$id/${approve ? 'approve' : 'reject'}/');
    summaries = [
      for (final s in summaries)
        if (s['id'] == id) updated else s,
    ];
  });

  Future<Json> fetchNote(int id) => api.get('/notes/$id/');
}
