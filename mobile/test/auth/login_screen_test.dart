import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/providers.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/core/theme/app_theme.dart';
import 'package:mebelchi_ai/features/authentication/presentation/login_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../support/fake_adapter.dart';

Future<FakeAdapter> _pump(WidgetTester t, Handler h, {String lang = 'en'}) async {
  SharedPreferences.setMockInitialValues({'mebelchi.language': lang});
  final prefs = await SharedPreferences.getInstance();
  final storage = MemoryTokenStorage();
  final adapter = FakeAdapter(h);
  await t.pumpWidget(ProviderScope(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
      tokenStorageProvider.overrideWithValue(storage),
      apiClientProvider.overrideWith((ref) => ApiClient(storage: storage, baseUrl: 'http://x/api/v1', adapter: adapter)),
    ],
    child: MaterialApp(theme: buildTheme(), home: const LoginScreen()),
  ));
  await t.pump();
  return adapter;
}

void main() {
  testWidgets('empty form shows validation errors and sends nothing', (t) async {
    final a = await _pump(t, (o) => (status: 200, body: {}));
    await t.tap(find.text('Sign in').last);
    await t.pump();
    expect(find.text('This field is required'), findsNWidgets(2));
    expect(a.log, isEmpty);
  });

  testWidgets('rejects a malformed email', (t) async {
    await _pump(t, (o) => (status: 200, body: {}));
    await t.enterText(find.byType(TextFormField).first, 'not-an-email');
    await t.enterText(find.byType(TextFormField).last, 'x');
    await t.tap(find.text('Sign in').last);
    await t.pump();
    expect(find.text('Enter a valid email address'), findsOneWidget);
  });

  testWidgets('wrong credentials show a clear message and stop the spinner', (t) async {
    final a = await _pump(t, (o) => (status: 401, body: {'error': {'status': 401, 'detail': 'No active account found'}}));
    await t.enterText(find.byType(TextFormField).first, 'a@b.co');
    await t.enterText(find.byType(TextFormField).last, 'wrongpass');
    await t.tap(find.text('Sign in').last);
    await t.pumpAndSettle();
    expect(find.text('Incorrect email or password'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(a.log.single.path, 'auth/login/');
  });

  testWidgets('the screen follows the chosen language', (t) async {
    await _pump(t, (o) => (status: 200, body: {}), lang: 'uz');
    expect(find.text('Hisobingizga kiring'), findsOneWidget);
  });

  testWidgets('password field can be revealed', (t) async {
    await _pump(t, (o) => (status: 200, body: {}));
    final field = find.byType(EditableText).last;
    expect(t.widget<EditableText>(field).obscureText, isTrue);
    await t.tap(find.byTooltip('Show password'));
    await t.pump();
    expect(t.widget<EditableText>(field).obscureText, isFalse);
  });
}
