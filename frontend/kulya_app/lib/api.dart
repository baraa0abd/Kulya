import 'package:dio/dio.dart';

typedef Json = Map<String, dynamic>;

/// Thin client for /api/v1. Same-origin by default, so it works behind Django or nginx unchanged.
/// Tokens live in memory only: reloading the page signs the user out.
class Api {
  Api({String baseUrl = '/api/v1', Dio? dio}) : dio = dio ?? Dio(BaseOptions(baseUrl: baseUrl)) {
    this.dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (_access != null && !options.path.startsWith('/auth/')) {
            options.headers['Authorization'] = 'Bearer $_access';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          final options = error.requestOptions;
          final expired = error.response?.statusCode == 401 && !options.path.startsWith('/auth/');
          if (!expired || _refresh == null || options.extra['retried'] == true) {
            return handler.next(error);
          }
          try {
            // Access tokens are short-lived; refresh once and replay the request.
            final fresh = await this.dio.post<Json>('/auth/token/refresh', data: {'refresh': _refresh});
            _access = fresh.data!['access'] as String;
            options.extra['retried'] = true;
            handler.resolve(await this.dio.fetch<dynamic>(options));
          } on DioException {
            handler.next(error);
          }
        },
      ),
    );
  }

  final Dio dio;
  String? _access;
  String? _refresh;

  Future<Json> login(String username, String password) async {
    final response = await dio.post<Json>('/auth/token', data: {'username': username, 'password': password});
    _access = response.data!['access'] as String;
    _refresh = response.data!['refresh'] as String;
    return response.data!;
  }

  void logout() => _access = _refresh = null;

  Future<Json> get(String path) async => (await dio.get<Json>(path)).data!;

  Future<Json> post(String path, [Object? body]) async => (await dio.post<Json>(path, data: body ?? {})).data!;

  /// Every page of a paginated list.
  Future<List<Json>> list(String path) async {
    final items = <Json>[];
    for (var page = 1; ; page++) {
      final data = await get('$path${path.contains('?') ? '&' : '?'}page=$page');
      items.addAll((data['results'] as List).cast<Json>());
      if (data['next'] == null) return items;
    }
  }
}

/// The backend's shared error format: {"error": {"code", "message_ar", "message_en", "details"}}.
class ApiFailure {
  ApiFailure(this.messageAr, this.messageEn, this.details);

  factory ApiFailure.from(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['error'] is Map) {
        final e = data['error'] as Map;
        return ApiFailure(e['message_ar'] as String?, e['message_en'] as String?, e['details']);
      }
    }
    return ApiFailure(null, null, null);
  }

  final String? messageAr;
  final String? messageEn;
  final Object? details;
}
