import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/providers.dart';

/// Bottom navigation for the signed-in area. Destinations are the same list for every role until a role gets its own screens
/// (see `routing/navigation.dart`); on wide screens (tablets) a rail replaces the bottom bar.
class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.shell});
  final StatefulNavigationShell shell;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final items = [
      (LucideIcons.house, s.t('nav.home')),
      (LucideIcons.folder, s.t('nav.projects')),
      (LucideIcons.armchair, s.t('nav.catalog')),
      (LucideIcons.box, s.t('nav.rooms')),
      (LucideIcons.user, s.t('nav.profile')),
    ];
    final wide = MediaQuery.sizeOf(context).width >= 720;
    void go(int i) => shell.goBranch(i, initialLocation: i == shell.currentIndex);
    if (wide) {
      return Scaffold(
        body: Row(children: [
          NavigationRail(
            selectedIndex: shell.currentIndex,
            onDestinationSelected: go,
            labelType: NavigationRailLabelType.all,
            destinations: [for (final i in items) NavigationRailDestination(icon: Icon(i.$1), label: Text(i.$2))],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: shell),
        ]),
      );
    }
    return Scaffold(
      body: shell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        onDestinationSelected: go,
        destinations: [for (final i in items) NavigationDestination(icon: Icon(i.$1), label: i.$2)],
      ),
    );
  }
}
