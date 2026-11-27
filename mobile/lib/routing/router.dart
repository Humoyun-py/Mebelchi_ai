import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../core/providers.dart';
import '../features/authentication/presentation/auth_controller.dart';
import '../features/authentication/presentation/forgot_password_screen.dart';
import '../features/authentication/presentation/login_screen.dart';
import '../features/authentication/presentation/register_screen.dart';
import '../features/authentication/presentation/role_screen.dart';
import '../features/calculator/presentation/calculator_screen.dart';
import '../features/dashboard/presentation/app_shell.dart';
import '../features/workshop_orders/presentation/orders_screens.dart';
import '../features/dashboard/presentation/home_screen.dart';
import '../features/furniture_catalog/presentation/catalog_screens.dart';
import '../features/profile/presentation/change_password_screen.dart';
import '../features/profile/presentation/edit_profile_screen.dart';
import '../features/profile/presentation/phone_verify_screen.dart';
import '../features/profile/presentation/profile_screen.dart';
import '../features/projects/presentation/projects_screens.dart';
import '../features/room_designer/presentation/room_wizard_screen.dart';
import '../features/room_designer/presentation/rooms_screen.dart';
import '../shared/widgets/app_button.dart';
import '../shared/widgets/state_views.dart';

const _publicPaths = {'/login', '/register', '/forgot'};

/// Pure routing rule (unit-tested): where must the user be, given the auth state and where they are now?
/// Returns null to stay.
String? redirectFor(AuthState auth, String location) {
  switch (auth.status) {
    case AuthStatus.unknown:
    case AuthStatus.failed:
      return location == '/splash' ? null : '/splash';
    case AuthStatus.unauthenticated:
      return _publicPaths.contains(location) ? null : '/login';
    case AuthStatus.authenticated:
      final u = auth.user!;
      if (u.needsRole) return location == '/role' ? null : '/role';
      if (location == '/splash' || location == '/role' || _publicPaths.contains(location)) return '/home';
      return null;
  }
}

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen<AuthState>(authControllerProvider, (_, _) => refresh.value++);
  ref.onDispose(refresh.dispose);

  final router = GoRouter(
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) => redirectFor(ref.read(authControllerProvider), state.uri.path),
    routes: [
      GoRoute(path: '/splash', builder: (_, _) => const _SplashScreen()),
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      GoRoute(path: '/register', builder: (_, _) => const RegisterScreen()),
      GoRoute(path: '/forgot', builder: (_, _) => const ForgotPasswordScreen()),
      GoRoute(path: '/role', builder: (_, _) => const RoleScreen()),
      GoRoute(path: '/calculator', builder: (_, st) => CalculatorScreen(projectId: int.tryParse(st.uri.queryParameters['project'] ?? ''))),
      GoRoute(path: '/orders', builder: (_, _) => const OrdersScreen(), routes: [
        GoRoute(path: ':id', builder: (_, st) => OrderDetailScreen(id: int.parse(st.pathParameters['id']!))),
      ]),
      StatefulShellRoute.indexedStack(
        builder: (_, _, shell) => AppShell(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (_, _) => const HomeScreen())]),
          StatefulShellBranch(routes: [
            GoRoute(path: '/projects', builder: (_, _) => const ProjectsScreen(), routes: [
              GoRoute(path: ':id', builder: (_, st) => ProjectDetailScreen(id: int.parse(st.pathParameters['id']!))),
            ]),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: '/catalog', builder: (_, _) => const CatalogScreen(), routes: [
              GoRoute(path: ':id', builder: (_, st) => FurnitureDetailScreen(id: int.parse(st.pathParameters['id']!))),
            ]),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: '/rooms', builder: (_, _) => const RoomsScreen(), routes: [
              GoRoute(path: ':id', builder: (_, st) => RoomWizardScreen(roomId: int.parse(st.pathParameters['id']!))),
            ]),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: '/profile', builder: (_, _) => const ProfileScreen(), routes: [
              GoRoute(path: 'edit', builder: (_, _) => const EditProfileScreen()),
              GoRoute(path: 'phone', builder: (_, _) => const PhoneVerifyScreen()),
              GoRoute(path: 'password', builder: (_, _) => const ChangePasswordScreen()),
            ]),
          ]),
        ],
      ),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});

class _SplashScreen extends ConsumerWidget {
  const _SplashScreen();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    final s = ref.watch(stringsProvider);
    return Scaffold(
      body: auth.status == AuthStatus.failed
          ? Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Expanded(child: ErrorView(error: auth.error!, onRetry: () => ref.read(authControllerProvider.notifier).bootstrap())),
              Padding(
                padding: const EdgeInsets.all(24),
                child: AppButton(label: s.t('common.logout'), outlined: true, icon: LucideIcons.logOut, onPressed: () => ref.read(authControllerProvider.notifier).logout()),
              ),
            ])
          : const LoadingView(),
    );
  }
}
