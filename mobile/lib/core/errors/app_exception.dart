import 'package:dio/dio.dart';

enum AppErrorKind { network, timeout, unauthorized, forbidden, notFound, validation, throttled, unavailable, server, cancelled, unknown }

/// The one error type the UI sees. The backend envelope is `{"error": {"status", "detail", "fields"?}}`.
class AppException implements Exception {
  const AppException(this.kind, {this.detail = '', this.status, this.fields = const {}});

  final AppErrorKind kind;
  final String detail; // server text, English; shown only for kinds where it is meaningful
  final int? status;
  final Map<String, List<String>> fields;

  /// First server message for a field, if any.
  String? fieldError(String name) => fields[name]?.firstOrNull;

  bool get isUnauthorized => kind == AppErrorKind.unauthorized;

  static AppException from(Object error) {
    if (error is AppException) return error;
    if (error is DioException) return _fromDio(error);
    return AppException(AppErrorKind.unknown, detail: error.toString());
  }

  static AppException _fromDio(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const AppException(AppErrorKind.timeout);
      case DioExceptionType.connectionError:
        return const AppException(AppErrorKind.network);
      case DioExceptionType.cancel:
        return const AppException(AppErrorKind.cancelled);
      default:
        break;
    }
    final res = e.response;
    if (res == null) return const AppException(AppErrorKind.network);
    final status = res.statusCode ?? 0;
    var detail = '';
    var fields = <String, List<String>>{};
    final data = res.data;
    if (data is Map && data['error'] is Map) {
      final err = data['error'] as Map;
      detail = (err['detail'] ?? '').toString();
      if (err['fields'] is Map) fields = _flatten(err['fields'] as Map);
    }
    final kind = switch (status) {
      400 || 422 => AppErrorKind.validation,
      401 => AppErrorKind.unauthorized,
      403 => AppErrorKind.forbidden,
      404 => AppErrorKind.notFound,
      429 => AppErrorKind.throttled,
      503 => AppErrorKind.unavailable,
      >= 500 => AppErrorKind.server,
      _ => AppErrorKind.unknown,
    };
    return AppException(kind, detail: detail, status: status, fields: fields);
  }

  static Map<String, List<String>> _flatten(Map src) {
    final out = <String, List<String>>{};
    src.forEach((k, v) {
      final key = k.toString();
      if (v is List) {
        out[key] = v.map((x) => x.toString()).toList();
      } else if (v is Map) {
        _flatten(v).forEach((sk, sv) => out['$key.$sk'] = sv);
      } else {
        out[key] = [v.toString()];
      }
    });
    return out;
  }

  @override
  String toString() => 'AppException($kind, $status, $detail)';
}
