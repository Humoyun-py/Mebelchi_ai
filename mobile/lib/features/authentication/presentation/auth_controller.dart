import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/providers.dart';
import '../domain/user.dart';

enum AuthStatus { unknown, unauthenticated, authenticated, failed }

class AuthState {
  const AuthState(this.status, {this.user, this.error});
  const AuthState.unknown() : this(AuthStatus.unknown);
  const AuthState.signedOut() : this(AuthStatus.unauthenticated);

  final AuthStatus status;
  final User? user;
  final Object? error;
}

/// Owns the signed-in user. The access/refresh tokens themselves live in [TokenStorage]; this only knows whether they work.
class AuthController extends Notifier<AuthState> {
  int _signIns = 0; // a sign-in that happens while a logout call is still running must keep its new tokens

  @override
  AuthState build() {
    Future.microtask(bootstrap);
    return const AuthState.unknown();
  }

  Future<void> bootstrap() async {
    state = const AuthState.unknown();
    final tokens = await ref.read(tokenStorageProvider).read();
    if (tokens == null) {
      state = const AuthState.signedOut();
      return;
    }
    try {
      final user = await ref.read(authRepositoryProvider).me();
      state = AuthState(AuthStatus.authenticated, user: user);
    } on AppException catch (e) {
      // 401 here means the refresh token is dead too (the client already cleared the tokens)
      state = e.isUnauthorized ? const AuthState.signedOut() : AuthState(AuthStatus.failed, error: e);
    }
  }

  Future<void> login(String email, String password) async {
    final s = await ref.read(authRepositoryProvider).login(email, password);
    _signIns++;
    await ref.read(tokenStorageProvider).write(s.tokens);
    state = AuthState(AuthStatus.authenticated, user: s.user);
  }

  Future<void> register({required String firstName, required String lastName, required String email, required String password, String phone = ''}) async {
    final s = await ref.read(authRepositoryProvider).register(firstName: firstName, lastName: lastName, email: email, password: password, phone: phone);
    _signIns++;
    await ref.read(tokenStorageProvider).write(s.tokens);
    state = AuthState(AuthStatus.authenticated, user: s.user);
  }

  Future<void> logout() async {
    final storage = ref.read(tokenStorageProvider);
    final tokens = await storage.read();
    // the UI leaves the app at once; the server call (blacklists the refresh token) is best effort and bounded,
    // so a dead network never traps the user. The tokens are removed from the device either way.
    final mine = _signIns;
    state = const AuthState.signedOut();
    try {
      if (tokens != null) await ref.read(authRepositoryProvider).logout(tokens.refresh).timeout(const Duration(seconds: 5));
    } catch (_) {
      // ignored on purpose
    } finally {
      if (mine == _signIns) await storage.clear();
    }
  }

  void sessionExpired() {
    if (state.status == AuthStatus.authenticated) state = const AuthState.signedOut();
  }

  void setUser(User user) => state = AuthState(AuthStatus.authenticated, user: user);

  Future<void> setRole(UserRole role) async => setUser(await ref.read(authRepositoryProvider).setRole(role));

  Future<void> updateProfile({String? firstName, String? lastName, String? phone, String? language}) async =>
      setUser(await ref.read(authRepositoryProvider).updateProfile(firstName: firstName, lastName: lastName, phone: phone, language: language));
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(AuthController.new);
