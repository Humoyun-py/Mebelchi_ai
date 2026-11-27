import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/config/env.dart';
import 'package:mebelchi_ai/core/errors/app_exception.dart';

DioException _err(int status, Object? data) {
  final o = RequestOptions(path: 'x');
  return DioException(requestOptions: o, type: DioExceptionType.badResponse, response: Response(requestOptions: o, statusCode: status, data: data));
}

void main() {
  test('maps the backend envelope with field errors', () {
    final e = AppException.from(_err(400, {'error': {'status': 400, 'detail': 'Validation failed.', 'fields': {'email': ['taken'], 'nested': {'a': ['b']}}}}));
    expect(e.kind, AppErrorKind.validation);
    expect(e.fieldError('email'), 'taken');
    expect(e.fieldError('nested.a'), 'b');
  });

  test('maps status codes to kinds', () {
    expect(AppException.from(_err(401, {})).kind, AppErrorKind.unauthorized);
    expect(AppException.from(_err(403, {})).kind, AppErrorKind.forbidden);
    expect(AppException.from(_err(404, {})).kind, AppErrorKind.notFound);
    expect(AppException.from(_err(429, {})).kind, AppErrorKind.throttled);
    expect(AppException.from(_err(503, {'error': {'detail': 'SMS is not configured'}})).detail, 'SMS is not configured');
    expect(AppException.from(_err(500, 'html')).kind, AppErrorKind.server);
  });

  test('network problems', () {
    final o = RequestOptions(path: 'x');
    expect(AppException.from(DioException.connectionError(requestOptions: o, reason: 'x')).kind, AppErrorKind.network);
    expect(AppException.from(DioException.connectionTimeout(requestOptions: o, timeout: const Duration(seconds: 1))).kind, AppErrorKind.timeout);
  });

  test('Env: release needs https; signed file links resolve against the server origin', () {
    expect(Env.isSecureOrDebug('http://x', isRelease: true), isFalse);
    expect(Env.isSecureOrDebug('https://x', isRelease: true), isTrue);
    expect(Env.isSecureOrDebug('http://x', isRelease: false), isTrue);
    expect(Env.isSecureOrDebug('http://192.168.1.5:8000', isRelease: true, test: true), isTrue);
    expect(Env.isSecureOrDebug('http://x', isRelease: true, test: false), isFalse);
    expect(Env.resolveUrl('/api/v1/users/1/avatar/?sig=abc', base: 'https://mebelchi.uz/api/v1'), 'https://mebelchi.uz/api/v1/users/1/avatar/?sig=abc');
    expect(Env.resolveUrl('https://cdn/x.png', base: 'https://mebelchi.uz/api/v1'), 'https://cdn/x.png');
  });
}
