import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'core/config/env.dart';
import 'core/providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (!Env.isSecureOrDebug(Env.apiBaseUrl, isRelease: kReleaseMode)) {
    throw StateError('Release builds need an https API_BASE_URL (--dart-define=API_BASE_URL=https://.../api/v1)');
  }
  final prefs = await SharedPreferences.getInstance();
  runApp(ProviderScope(overrides: [sharedPreferencesProvider.overrideWithValue(prefs)], child: const MebelchiApp()));
}
