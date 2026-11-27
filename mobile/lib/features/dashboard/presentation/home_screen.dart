import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/l10n/strings.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../authentication/domain/user.dart';
import '../../authentication/presentation/auth_controller.dart';

String roleLabel(S s, User u) {
  if (u.isAdmin) return s.t('role.admin');
  return switch (u.role) {
    UserRole.homeowner => s.t('role.homeowner'),
    UserRole.maker => s.t('role.maker'),
    UserRole.workshop => s.t('role.workshop'),
  };
}

/// Landing screen of every role. Role-specific sections are added here as their phases ship, and only then:
/// no button appears before the feature behind it works.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final user = ref.watch(authControllerProvider).user;
    if (user == null) return const SizedBox.shrink();
    final name = user.firstName.isEmpty ? user.email : user.firstName;
    return Scaffold(
      appBar: AppBar(title: const Text('Mebelchi AI', style: TextStyle(fontWeight: FontWeight.w700))),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: ListView(padding: const EdgeInsets.all(AppSpacing.lg), children: [
              Text(s.f('home.welcome', {'name': name}), style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700)),
              const SizedBox(height: AppSpacing.sm),
              Row(children: [
                const Icon(LucideIcons.shieldCheck, size: 18, color: AppColors.textMuted),
                const SizedBox(width: 8),
                Text(s.f('home.roleLine', {'role': roleLabel(s, user)}), style: const TextStyle(color: AppColors.textMuted)),
              ]),
              const SizedBox(height: AppSpacing.lg),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(s.t('home.status'), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                    const SizedBox(height: AppSpacing.md),
                    Row(children: [
                      Icon(user.phoneVerified ? LucideIcons.check : LucideIcons.phone, size: 20, color: user.phoneVerified ? AppColors.success : AppColors.textMuted),
                      const SizedBox(width: 12),
                      Expanded(child: Text(user.phoneVerified ? s.t('home.phoneVerified') : s.t('home.phoneNotVerified'))),
                      if (!user.phoneVerified) TextButton(onPressed: () => context.push('/profile/phone'), child: Text(s.t('home.phoneVerifyAction'))),
                    ]),
                  ]),
                ),
              ),
              if (user.role == UserRole.workshop) ...[
                const SizedBox(height: AppSpacing.md),
                Card(
                  child: ListTile(
                    leading: const Icon(LucideIcons.packageOpen),
                    title: Text(s.t('home.orders'), style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text(s.t('home.orders.sub')),
                    trailing: const Icon(LucideIcons.chevronRight),
                    onTap: () => context.push('/orders'),
                  ),
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              Card(
                child: ListTile(
                  leading: const Icon(LucideIcons.calculator),
                  title: Text(s.t('home.calculator'), style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text(s.t('calc.unitsNote')),
                  trailing: const Icon(LucideIcons.chevronRight),
                  onTap: () => context.push('/calculator'),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              Card(
                color: AppColors.surfaceAlt,
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(s.t('home.noteTitle'), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                    const SizedBox(height: 6),
                    Text(s.t('home.noteBody'), style: const TextStyle(color: AppColors.textMuted)),
                  ]),
                ),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
