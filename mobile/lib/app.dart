import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/providers.dart';
import 'core/theme/app_theme.dart';
import 'routing/router.dart';

class MebelchiApp extends ConsumerWidget {
  const MebelchiApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'Mebelchi AI',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      routerConfig: ref.watch(routerProvider),
      locale: Locale(ref.watch(languageProvider)),
      supportedLocales: const [Locale('uz'), Locale('ru'), Locale('en')],
    );
  }
}
