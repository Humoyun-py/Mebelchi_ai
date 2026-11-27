import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/config/env.dart';
import '../../../core/l10n/strings.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../authentication/domain/user.dart';
import '../../authentication/presentation/auth_controller.dart';
import '../../dashboard/presentation/home_screen.dart';

class UserAvatar extends StatelessWidget {
  const UserAvatar({super.key, required this.user, this.size = 72});
  final User user;
  final double size;

  @override
  Widget build(BuildContext context) {
    final initials = ((user.firstName.isNotEmpty ? user.firstName[0] : '') + (user.lastName.isNotEmpty ? user.lastName[0] : '')).toUpperCase();
    final fallback = Center(child: Text(initials.isEmpty ? '?' : initials, style: TextStyle(color: AppColors.accent, fontSize: size / 2.6, fontWeight: FontWeight.w700)));
    return ClipOval(
      child: Container(
        width: size,
        height: size,
        color: AppColors.primary,
        child: user.avatarUrl == null
            ? fallback
            : CachedNetworkImage(
                imageUrl: Env.resolveUrl(user.avatarUrl!),
                cacheKey: 'avatar-${user.id}',
                fit: BoxFit.cover,
                errorWidget: (_, _, _) => fallback,
                placeholder: (_, _) => fallback,
              ),
      ),
    );
  }
}

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  Future<void> _logout(BuildContext context, WidgetRef ref, S s) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(s.t('profile.logout.confirm')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: Text(s.t('common.cancel'))),
          TextButton(onPressed: () => Navigator.pop(c, true), child: Text(s.t('common.logout'))),
        ],
      ),
    );
    if (ok == true) await ref.read(authControllerProvider.notifier).logout();
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final user = ref.watch(authControllerProvider).user;
    if (user == null) return const SizedBox.shrink();
    final lang = ref.watch(languageProvider);
    return Scaffold(
      appBar: AppBar(title: Text(s.t('profile.title'), style: const TextStyle(fontWeight: FontWeight.w700))),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: ListView(padding: const EdgeInsets.all(AppSpacing.lg), children: [
              Row(children: [
                UserAvatar(user: user),
                const SizedBox(width: AppSpacing.md),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(user.fullName.isEmpty ? user.email : user.fullName, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 2),
                  Text(user.email, style: const TextStyle(color: AppColors.textMuted), overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 2),
                  Text(roleLabel(s, user), style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
                ])),
              ]),
              const SizedBox(height: AppSpacing.lg),
              Card(
                child: Column(children: [
                  _Tile(icon: LucideIcons.pencil, title: s.t('profile.edit'), onTap: () => context.push('/profile/edit')),
                  const Divider(height: 1),
                  _Tile(
                    icon: LucideIcons.phone,
                    title: s.t('profile.phone'),
                    trailingText: user.phone.isEmpty ? null : (user.phoneVerified ? s.t('profile.phone.verified') : s.t('home.phoneNotVerified')),
                    onTap: () => context.push('/profile/phone'),
                  ),
                  const Divider(height: 1),
                  _Tile(icon: LucideIcons.key, title: s.t('profile.password'), onTap: () => context.push('/profile/password')),
                  const Divider(height: 1),
                  _Tile(icon: LucideIcons.globe, title: s.t('profile.language'), trailingText: languageNames[lang], onTap: () => _pickLanguage(context, ref, s, lang)),
                ]),
              ),
              const SizedBox(height: AppSpacing.lg),
              OutlinedButton.icon(onPressed: () => _logout(context, ref, s), icon: const Icon(LucideIcons.logOut, size: 20), label: Text(s.t('common.logout'))),
            ]),
          ),
        ),
      ),
    );
  }

  Future<void> _pickLanguage(BuildContext context, WidgetRef ref, S s, String current) async {
    final picked = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (c) => SafeArea(
        child: RadioGroup<String>(
          groupValue: current,
          onChanged: (v) => Navigator.pop(c, v),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            for (final l in supportedLanguages) RadioListTile<String>(value: l, title: Text(languageNames[l]!)),
          ]),
        ),
      ),
    );
    if (picked == null || picked == current) return;
    await ref.read(languageProvider.notifier).set(picked);
    try {
      await ref.read(authControllerProvider.notifier).updateProfile(language: picked); // keep the web/Telegram language in step; best effort
    } catch (_) {}
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.icon, required this.title, required this.onTap, this.trailingText});
  final IconData icon;
  final String title;
  final String? trailingText;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => ListTile(
        leading: Icon(icon, size: 22),
        title: Text(title),
        trailing: Row(mainAxisSize: MainAxisSize.min, children: [
          if (trailingText != null) Text(trailingText!, style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
          const SizedBox(width: 4),
          const Icon(LucideIcons.chevronRight, size: 20),
        ]),
        onTap: onTap,
      );
}
