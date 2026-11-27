// Runs the real app code (ApiClient, AuthRepository, AuthController) against a live Django server.
// Skipped unless MEBELCHI_E2E_URL is set, e.g.  MEBELCHI_E2E_URL=http://127.0.0.1:8765/api/v1 flutter test test/e2e
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/errors/app_exception.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/providers.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/authentication/domain/user.dart';
import 'package:mebelchi_ai/features/authentication/presentation/auth_controller.dart';

void main() {
  final url = Platform.environment['MEBELCHI_E2E_URL'];
  final skip = url == null ? 'set MEBELCHI_E2E_URL to run against a live server' : false;

  test('register, role, profile, token rotation, logout against the real backend', () async {
    final storage = MemoryTokenStorage();
    final c = ProviderContainer(overrides: [
      tokenStorageProvider.overrideWithValue(storage),
      apiClientProvider.overrideWith((ref) => ApiClient(storage: storage, baseUrl: url!, onSessionExpired: () => ref.read(authControllerProvider.notifier).sessionExpired())),
    ]);
    addTearDown(c.dispose);
    c.listen(authControllerProvider, (_, _) {});
    await Future<void>.delayed(const Duration(milliseconds: 300));
    final auth = c.read(authControllerProvider.notifier);
    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);

    final email = 'e2e${DateTime.now().microsecondsSinceEpoch}@example.com';
    // server-side validation reaches the app as field errors
    try {
      await auth.register(firstName: 'Ali', lastName: 'Valiyev', email: email, password: '123');
      fail('weak password must be rejected');
    } on AppException catch (e) {
      expect(e.kind, AppErrorKind.validation);
      expect(e.fields, isNotEmpty);
    }

    await auth.register(firstName: 'Ali', lastName: 'Valiyev', email: email, password: 'Str0ng-pass-2026');
    var st = c.read(authControllerProvider);
    expect(st.status, AuthStatus.authenticated);
    expect(st.user!.needsRole, isTrue);

    await auth.setRole(UserRole.maker);
    expect(c.read(authControllerProvider).user!.role, UserRole.maker);
    expect(c.read(authControllerProvider).user!.needsRole, isFalse);

    await auth.updateProfile(firstName: 'Alisher', language: 'uz');
    expect(c.read(authControllerProvider).user!.firstName, 'Alisher');

    // expire the access token on purpose: the next call must refresh transparently and rotate the refresh token
    final before = (await storage.read())!;
    await storage.write(Tokens(access: 'garbage', refresh: before.refresh));
    final me = await c.read(authRepositoryProvider).me();
    expect(me.email, email);
    final after = (await storage.read())!;
    expect(after.access, isNot('garbage'));
    expect(after.refresh, isNot(before.refresh));

    // the old (rotated) refresh token is blacklisted: reusing it ends the session
    await storage.write(Tokens(access: 'garbage', refresh: before.refresh));
    await expectLater(c.read(authRepositoryProvider).me(), throwsA(isA<AppException>().having((e) => e.isUnauthorized, 'unauthorized', true)));
    expect(await storage.read(), isNull);
    expect(c.read(authControllerProvider).status, AuthStatus.unauthenticated);

    // wrong password
    await expectLater(auth.login(email, 'wrong-password'), throwsA(isA<AppException>().having((e) => e.isUnauthorized, 'unauthorized', true)));
    // right password, then logout blacklists the refresh token
    await auth.login(email, 'Str0ng-pass-2026');
    final t = (await storage.read())!;
    await auth.logout();
    expect(await storage.read(), isNull);
    // logout blacklists the refresh token (the short-lived access token simply runs out), so it can no longer start a session
    await storage.write(Tokens(access: 'garbage', refresh: t.refresh));
    await expectLater(c.read(authRepositoryProvider).me(), throwsA(isA<AppException>().having((e) => e.isUnauthorized, 'unauthorized', true)));
  }, skip: skip);
}
