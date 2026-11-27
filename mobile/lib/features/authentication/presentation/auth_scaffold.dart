import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/l10n/strings.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';

/// Common frame for the sign-in screens: brand header, scrollable form column that stays readable on tablets.
class AuthScaffold extends ConsumerWidget {
  const AuthScaffold({super.key, required this.title, this.subtitle, required this.children, this.showBack = false});
  final String title;
  final String? subtitle;
  final List<Widget> children;
  final bool showBack;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(languageProvider);
    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: showBack,
        actions: [
          PopupMenuButton<String>(
            tooltip: ref.watch(stringsProvider).t('profile.language'),
            icon: const Icon(LucideIcons.languages),
            initialValue: lang,
            onSelected: (v) => ref.read(languageProvider.notifier).set(v),
            itemBuilder: (_) => [for (final l in supportedLanguages) PopupMenuItem(value: l, child: Text(languageNames[l]!))],
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Row(children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(color: AppColors.primary, borderRadius: BorderRadius.circular(12)),
                    child: const Icon(LucideIcons.sofa, color: AppColors.accent, size: 24),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  const Text('Mebelchi AI', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
                ]),
                const SizedBox(height: AppSpacing.xl),
                Text(title, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700), semanticsLabel: title),
                if (subtitle != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(subtitle!, style: const TextStyle(color: AppColors.textMuted, fontSize: 15)),
                ],
                const SizedBox(height: AppSpacing.lg),
                ...children,
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
