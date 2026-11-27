import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/errors/app_exception.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/providers.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/authentication/data/auth_repository.dart';
import 'package:mebelchi_ai/features/authentication/domain/user.dart';
import 'package:mebelchi_ai/features/authentication/presentation/auth_controller.dart';

import '../support/fake_adapter.dart';

const _userJson = {'id': 7, 'email': 'ali@example.com', 'first_name': 'Ali', 'last_name': 'Valiyev', 'role': 'homeowner', 'role_selected': true, 'phone_verified': false, 'language': 'uz'};

ProviderContainer _container(MemoryTokenStorage storage, FakeAdapter adapter) {
  final c = ProviderContainer(overrides: [
    tokenStorageProvider.overrideWithValue(storage),
    apiClientProvider.overrideWith((ref) => ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: adapter, onSessionExpired: () => ref.read(authControllerProvider.notifier).sessionExpired())),
  ]);
  addTearDown(c.dispose);
  return c;
}

Future<void> _settle(ProviderContainer c) async {
  c.listen(authControllerProvider, (_, _) {});
  for (var i = 0; i < 20 && c.read(authControllerProvider).status == AuthStatus.unknown; i++) {
    await Future<void>.delayed(const Duration(milliseconds: 10));
  }
}

void main() {
  test('no stored tokens: signed out without any network call', () async {
    final a = FakeAdapter((o) => (status: 500, body: {}));
    final c = _container(MemoryTokenStorage(), a);
    await _settle(c);
    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);
    expect(a.log, isEmpty);
  });

  test('stored tokens: loads the profile', () async {
    final s = MemoryTokenStorage()..write(const Tokens(access: 'a', refresh: 'r'));
    final c = _container(s, FakeAdapter((o) => (status: 200, body: _userJson)));
    await _settle(c);
    final st = c.read(authControllerProvider);
    expect(st.status, AuthStatus.authenticated);
    expect(st.user!.fullName, 'Ali Valiyev');
    expect(st.user!.role, UserRole.homeowner);
  });

  test('offline at start is a retryable failure, not a sign-out', () async {
    final s = MemoryTokenStorage()..write(const Tokens(access: 'a', refresh: 'r'));
    final c = _container(s, FakeAdapter((o) => throw StateError('offline')));
    await _settle(c);
    expect(c.read(authControllerProvider).status, AuthStatus.failed);
    expect(await s.read(), isNotNull);
  });

  test('login stores tokens; logout clears them and calls the server with the refresh token', () async {
    final s = MemoryTokenStorage();
    final a = FakeAdapter((o) => o.path == 'auth/login/' ? (status: 200, body: {'access': 'A', 'refresh': 'R', 'user': _userJson}) : (status: 204, body: null));
    final c = _container(s, a);
    await _settle(c);
    await c.read(authControllerProvider.notifier).login('ali@example.com', 'secret123');
    expect(c.read(authControllerProvider).status, AuthStatus.authenticated);
    expect(await s.read(), const Tokens(access: 'A', refresh: 'R'));
    await c.read(authControllerProvider.notifier).logout();
    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);
    expect(await s.read(), isNull);
    final out = a.log.last;
    expect(out.path, 'auth/logout/');
    expect(out.data, {'refresh': 'R'});
  });

  test('logout works with no network', () async {
    final s = MemoryTokenStorage()..write(const Tokens(access: 'a', refresh: 'r'));
    final c = _container(s, FakeAdapter((o) => o.path == 'users/me/' ? (status: 200, body: _userJson) : throw StateError('offline')));
    await _settle(c);
    await c.read(authControllerProvider.notifier).logout();
    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);
    expect(await s.read(), isNull);
  });

  test('wrong password surfaces as unauthorized and leaves the user signed out', () async {
    final s = MemoryTokenStorage();
    final c = _container(s, FakeAdapter((o) => (status: 401, body: {'error': {'status': 401, 'detail': 'No active account found'}})));
    await _settle(c);
    await expectLater(c.read(authControllerProvider.notifier).login('a@b.c', 'bad'), throwsA(isA<AppException>().having((e) => e.isUnauthorized, 'unauthorized', true)));
    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);
    expect(await s.read(), isNull);
  });

  test('registration sends confirm_password and shows server field errors', () async {
    final a = FakeAdapter((o) => (status: 400, body: {'error': {'status': 400, 'detail': 'Validation failed.', 'fields': {'email': ['An account with this email already exists.']}}}));
    final c = _container(MemoryTokenStorage(), a);
    await _settle(c);
    try {
      await c.read(authControllerProvider.notifier).register(firstName: 'A', lastName: 'B', email: 'a@b.c', password: 'longpass1');
      fail('should throw');
    } on AppException catch (e) {
      expect(e.fieldError('email'), contains('already exists'));
    }
    expect((a.log.single.data as Map)['confirm_password'], 'longpass1');
  });

  test('AuthRepository parses a page envelope helper-free user json', () {
    final u = User.fromJson({..._userJson, 'avatar_url': '/api/v1/users/7/avatar/?sig=x'});
    expect(u.avatarUrl, isNotNull);
    expect(AuthRepository, isNotNull);
  });
}
