import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/app.dart';
import 'package:mebelchi_ai/core/providers.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  // Regression: with the uz or ru locale the login screen showed a grey box (no MaterialLocalizations for these languages).
  for (final lang in ['uz', 'ru', 'en']) {
    testWidgets('the sign-in form renders in $lang', (t) async {
      SharedPreferences.setMockInitialValues({'mebelchi.language': lang});
      final prefs = await SharedPreferences.getInstance();
      await t.pumpWidget(ProviderScope(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs), tokenStorageProvider.overrideWithValue(MemoryTokenStorage())],
        child: const MebelchiApp(),
      ));
      await t.pumpAndSettle();
      expect(t.takeException(), isNull);
      expect(find.byType(TextFormField), findsWidgets);
      expect(Localizations.of<MaterialLocalizations>(t.element(find.byType(Scaffold).first), MaterialLocalizations), isNotNull);
    });
  }
}
