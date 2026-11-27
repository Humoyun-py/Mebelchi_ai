import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/features/authentication/domain/user.dart';
import 'package:mebelchi_ai/features/authentication/presentation/auth_controller.dart';
import 'package:mebelchi_ai/routing/router.dart';

User user({String role = 'homeowner', bool selected = true, bool admin = false}) => User.fromJson({'id': 1, 'email': 'a@b.c', 'role': role, 'role_selected': selected, 'is_admin': admin});

void main() {
  test('unknown or failed bootstrap stays on the splash screen', () {
    expect(redirectFor(const AuthState.unknown(), '/home'), '/splash');
    expect(redirectFor(const AuthState(AuthStatus.failed), '/login'), '/splash');
    expect(redirectFor(const AuthState.unknown(), '/splash'), isNull);
  });

  test('signed-out users only see the public screens', () {
    const out = AuthState.signedOut();
    expect(redirectFor(out, '/home'), '/login');
    expect(redirectFor(out, '/profile/phone'), '/login');
    expect(redirectFor(out, '/register'), isNull);
    expect(redirectFor(out, '/forgot'), isNull);
  });

  test('a new user must choose a role first; workshops and staff never do', () {
    expect(redirectFor(AuthState(AuthStatus.authenticated, user: user(selected: false)), '/home'), '/role');
    expect(redirectFor(AuthState(AuthStatus.authenticated, user: user(selected: false)), '/role'), isNull);
    expect(redirectFor(AuthState(AuthStatus.authenticated, user: user(role: 'workshop', selected: false)), '/splash'), '/home');
    expect(redirectFor(AuthState(AuthStatus.authenticated, user: user(selected: false, admin: true)), '/splash'), '/home');
  });

  test('signed-in users leave the auth screens', () {
    final a = AuthState(AuthStatus.authenticated, user: user());
    expect(redirectFor(a, '/login'), '/home');
    expect(redirectFor(a, '/role'), '/home');
    expect(redirectFor(a, '/profile'), isNull);
  });
}
