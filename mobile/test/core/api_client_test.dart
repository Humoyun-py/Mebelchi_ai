import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/errors/app_exception.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';

import '../support/fake_adapter.dart';

void main() {
  late MemoryTokenStorage storage;

  setUp(() async {
    storage = MemoryTokenStorage();
    await storage.write(const Tokens(access: 'old', refresh: 'r1'));
  });

  test('adds the bearer token', () async {
    final a = FakeAdapter((o) => (status: 200, body: {'ok': true}));
    final api = ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: a);
    await api.dio.get('users/me/');
    expect(a.log.single.headers['Authorization'], 'Bearer old');
    expect(a.log.single.uri.toString(), 'http://x/api/v1/users/me/');
  });

  test('noAuth requests carry no token', () async {
    final a = FakeAdapter((o) => (status: 200, body: {}));
    final api = ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: a);
    await api.dio.post('auth/login/', data: {}, options: noAuth);
    expect(a.log.single.headers.containsKey('Authorization'), isFalse);
  });

  test('401 refreshes once, stores the rotated tokens and retries the request', () async {
    final a = FakeAdapter((o) {
      if (o.path == 'auth/refresh/') return (status: 200, body: {'access': 'new', 'refresh': 'r2'});
      return o.headers['Authorization'] == 'Bearer new' ? (status: 200, body: {'id': 1}) : (status: 401, body: {'error': {'status': 401, 'detail': 'expired'}});
    });
    final api = ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: a);
    final r = await api.dio.get('users/me/');
    expect(r.data, {'id': 1});
    expect(await storage.read(), const Tokens(access: 'new', refresh: 'r2'));
    expect(a.log.where((o) => o.path == 'auth/refresh/').length, 1);
  });

  test('several parallel 401s share one refresh call', () async {
    final a = FakeAdapter((o) {
      if (o.path == 'auth/refresh/') return (status: 200, body: {'access': 'new', 'refresh': 'r2'});
      return o.headers['Authorization'] == 'Bearer new' ? (status: 200, body: {}) : (status: 401, body: {});
    });
    final api = ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: a);
    await Future.wait([for (var i = 0; i < 5; i++) api.dio.get('projects/')]);
    expect(a.log.where((o) => o.path == 'auth/refresh/').length, 1);
  });

  test('a dead refresh token clears the session and reports it once', () async {
    var expired = 0;
    final a = FakeAdapter((o) => o.path == 'auth/refresh/' ? (status: 401, body: {'error': {'status': 401, 'detail': 'bad'}}) : (status: 401, body: {}));
    final api = ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: a, onSessionExpired: () => expired++);
    await expectLater(api.guard(() => api.dio.get('users/me/')), throwsA(isA<AppException>().having((e) => e.kind, 'kind', AppErrorKind.unauthorized)));
    expect(await storage.read(), isNull);
    expect(expired, 1);
  });

  test('a failing refresh because of the network keeps the session', () async {
    var expired = 0;
    final a = FakeAdapter((o) {
      if (o.path == 'auth/refresh/') throw DioException.connectionError(requestOptions: o, reason: 'offline');
      return (status: 401, body: {});
    });
    final api = ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: a, onSessionExpired: () => expired++);
    await expectLater(api.guard(() => api.dio.get('users/me/')), throwsA(isA<AppException>()));
    expect(await storage.read(), isNotNull);
    expect(expired, 0);
  });

  test('login 401 does not trigger a refresh', () async {
    final a = FakeAdapter((o) => (status: 401, body: {'error': {'status': 401, 'detail': 'No active account'}}));
    final api = ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: a);
    await expectLater(api.guard(() => api.dio.post('auth/login/', data: {}, options: noAuth)), throwsA(isA<AppException>()));
    expect(a.log.where((o) => o.path == 'auth/refresh/'), isEmpty);
  });
}
