import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/state_views.dart';
import '../domain/user.dart';
import 'auth_controller.dart';
import 'auth_scaffold.dart';

/// First sign-in: the user picks "home owner" or "furniture maker". Workshops are assigned by an administrator, so they are not offered.
class RoleScreen extends ConsumerStatefulWidget {
  const RoleScreen({super.key});
  @override
  ConsumerState<RoleScreen> createState() => _RoleScreenState();
}

class _RoleScreenState extends ConsumerState<RoleScreen> {
  UserRole? _busy;
  Object? _error;

  Future<void> _pick(UserRole r) async {
    if (_busy != null) return;
    setState(() {
      _busy = r;
      _error = null;
    });
    try {
      await ref.read(authControllerProvider.notifier).setRole(r);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    return AuthScaffold(
      title: s.t('role.title'),
      subtitle: s.t('role.subtitle'),
      children: [
        if (_error != null) ...[FormError(s.error(_error!)), const SizedBox(height: 16)],
        _RoleCard(icon: LucideIcons.house, title: s.t('role.homeowner'), body: s.t('role.homeowner.desc'), loading: _busy == UserRole.homeowner, onTap: () => _pick(UserRole.homeowner)),
        const SizedBox(height: 12),
        _RoleCard(icon: LucideIcons.hammer, title: s.t('role.maker'), body: s.t('role.maker.desc'), loading: _busy == UserRole.maker, onTap: () => _pick(UserRole.maker)),
        const SizedBox(height: 16),
        Text(s.t('role.workshopNote'), style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
        const SizedBox(height: 16),
        TextButton(onPressed: () => ref.read(authControllerProvider.notifier).logout(), child: Text(s.t('common.logout'))),
      ],
    );
  }
}

class _RoleCard extends StatelessWidget {
  const _RoleCard({required this.icon, required this.title, required this.body, required this.onTap, required this.loading});
  final IconData icon;
  final String title;
  final String body;
  final VoidCallback onTap;
  final bool loading;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: '$title. $body',
        child: Card(
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Row(children: [
                Container(width: 48, height: 48, decoration: BoxDecoration(color: AppColors.primary, borderRadius: BorderRadius.circular(12)), child: Icon(icon, color: AppColors.accent)),
                const SizedBox(width: AppSpacing.md),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(body, style: const TextStyle(color: AppColors.textMuted)),
                ])),
                loading ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5)) : const Icon(LucideIcons.chevronRight),
              ]),
            ),
          ),
        ),
      );
}
