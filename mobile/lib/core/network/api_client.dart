import 'dart:async';

import 'package:dio/dio.dart';

import '../errors/app_exception.dart';
import '../storage/token_storage.dart';

const _retriedKey = 'mebelchi.retried';
const _noAuthKey = 'mebelchi.noAuth';
const _netRetryKey = 'mebelchi.netRetried';

/// Options for endpoints that must be called without a bearer token (login, register, refresh, password reset).
Options get noAuth => Options(extra: {_noAuthKey: true});

/// Dio wrapper: bearer header, one shared token refresh when several requests hit 401 together, one retry.
class ApiClient {
  ApiClient({required TokenStorage storage, required String baseUrl, HttpClientAdapter? adapter, this.onSessionExpired})
      : _storage = storage,
        dio = Dio(BaseOptions(
          baseUrl: baseUrl.endsWith('/') ? baseUrl : '$baseUrl/',
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 30),
          sendTimeout: const Duration(seconds: 30),
          headers: {'Accept': 'application/json'},
        )),
        _refreshDio = Dio(BaseOptions(
          baseUrl: baseUrl.endsWith('/') ? baseUrl : '$baseUrl/',
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 30),
        )) {
    if (adapter != null) {
      dio.httpClientAdapter = adapter;
      _refreshDio.httpClientAdapter = adapter;
    }
    dio.interceptors.add(InterceptorsWrapper(onRequest: _onRequest, onError: _onError));
  }

  final Dio dio;
  final Dio _refreshDio;
  final TokenStorage _storage;
  final void Function()? onSessionExpired;
  Future<bool>? _refreshing;

  Future<void> _onRequest(RequestOptions o, RequestInterceptorHandler h) async {
    if (o.extra[_noAuthKey] != true) {
      final t = await _storage.read();
      if (t != null) o.headers['Authorization'] = 'Bearer ${t.access}';
    }
    h.next(o);
  }

  Future<void> _onError(DioException e, ErrorInterceptorHandler h) async {
    final o = e.requestOptions;
    // A dropped connection (a keep-alive socket the server already closed, a brief signal loss) is retried once, for reads only: a GET can
    // never change data, so repeating it is safe. Writes are never repeated automatically.
    if (e.type == DioExceptionType.connectionError && o.method == 'GET' && o.extra[_netRetryKey] != true) {
      o.extra[_netRetryKey] = true;
      await Future<void>.delayed(const Duration(milliseconds: 400));
      try {
        return h.resolve(await dio.fetch(o));
      } on DioException catch (err) {
        return h.next(err);
      }
    }
    if (e.response?.statusCode != 401 || o.extra[_noAuthKey] == true || o.extra[_retriedKey] == true) return h.next(e);
    final sent = o.headers['Authorization'];
    final current = await _storage.read();
    if (current == null) return h.next(e);
    // another request already refreshed while this one was in flight: just retry with the new token
    var ok = 'Bearer ${current.access}' != sent;
    if (!ok) ok = await _refresh();
    if (!ok) return h.next(e);
    try {
      o.extra[_retriedKey] = true;
      h.resolve(await dio.fetch(o));
    } on DioException catch (err) {
      h.next(err);
    }
  }

  Future<bool> _refresh() {
    final running = _refreshing;
    if (running != null) return running;
    final f = _doRefresh().whenComplete(() => _refreshing = null);
    _refreshing = f;
    return f;
  }

  Future<bool> _doRefresh() async {
    final t = await _storage.read();
    if (t == null) return false;
    try {
      final r = await _refreshDio.post('auth/refresh/', data: {'refresh': t.refresh});
      final data = r.data as Map;
      final access = data['access']?.toString();
      if (access == null || access.isEmpty) throw StateError('no access token');
      // rotation is on: the server returns a new refresh token and blacklists the old one
      await _storage.write(Tokens(access: access, refresh: (data['refresh'] ?? t.refresh).toString()));
      return true;
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      if (code == 401 || code == 400 || code == 403) {
        await _storage.clear();
        onSessionExpired?.call();
      }
      return false; // network trouble keeps the session; the caller sees the original error
    } catch (_) {
      return false;
    }
  }

  /// Runs a request and converts every failure into [AppException].
  Future<T> guard<T>(Future<T> Function() run) async {
    try {
      return await run();
    } catch (e) {
      throw AppException.from(e);
    }
  }
}
