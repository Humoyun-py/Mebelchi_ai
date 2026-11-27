// Drives the real app on a device or emulator against a live backend.
//   flutter test integration_test -d <device> --dart-define=API_BASE_URL=http://10.0.2.2:8765/api/v1 --dart-define=E2E_PAUSE=1
// Needs a throwaway backend (it registers a user). E2E_PAUSE keeps the 3D screen open for a few seconds so it can be screenshotted.
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:mebelchi_ai/core/config/env.dart';
import 'package:mebelchi_ai/main.dart' as app;
import 'package:shared_preferences/shared_preferences.dart';

Future<void> _register(String email) async {
  final c = HttpClient();
  final req = await c.postUrl(Uri.parse('${Env.apiBaseUrl}/auth/register/'));
  req.headers.contentType = ContentType.json;
  final bytes = utf8.encode(jsonEncode({'first_name': 'Ali', 'last_name': 'Valiyev', 'email': email, 'password': 'Str0ng-pass-2026', 'confirm_password': 'Str0ng-pass-2026'}));
  req.contentLength = bytes.length; // the Django dev server does not accept chunked bodies
  req.add(bytes);
  final res = await req.close();
  final body = await res.transform(utf8.decoder).join();
  expect(res.statusCode, 201, reason: body);
  c.close();
}

Future<void> _settle(WidgetTester t, {int seconds = 6}) async {
  for (var i = 0; i < seconds * 4; i++) {
    await t.pump(const Duration(milliseconds: 250));
  }
}

Future<void> _until(WidgetTester t, Finder f, {int seconds = 20}) async {
  for (var i = 0; i < seconds * 4; i++) {
    await t.pump(const Duration(milliseconds: 250));
    if (f.evaluate().isNotEmpty) return;
  }
  fail('not found: $f');
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  const pause = String.fromEnvironment('E2E_PAUSE');

  testWidgets('sign in, choose role, browse catalogue, design a room end to end', (t) async {
    final email = 'device${DateTime.now().microsecondsSinceEpoch}@example.com';
    await _register(email);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('mebelchi.language', 'en');

    app.main();
    await _until(t, find.text('Sign in to your account'));
    await t.enterText(find.byType(TextFormField).first, email);
    await t.enterText(find.byType(TextFormField).last, 'Str0ng-pass-2026');
    await t.tap(find.text('Sign in').last);
    await _until(t, find.text('Who are you?'));
    await t.tap(find.text('Home owner'));
    await _until(t, find.textContaining('Hello, Ali'));
    expect(find.text('Phone not verified'), findsOneWidget);

    // catalogue
    await t.tap(find.text('Catalogue'));
    await _until(t, find.byType(ListTile));
    await t.tap(find.byType(ListTile).first);
    await _until(t, find.text('Add to a room design'));
    await t.pageBack();
    await _settle(t, seconds: 1);

    // room designer
    await t.tap(find.text('Designs'));
    await _until(t, find.text('New design'));
    await t.tap(find.text('New design'));
    await _until(t, find.text('Bedroom'));
    await t.tap(find.text('Bedroom'));
    await _until(t, find.text('Skip'));
    await t.tap(find.text('Skip'));
    await _until(t, find.text('Continue'));
    await t.tap(find.text('Continue')); // elements: 1 door, 1 window
    await _until(t, find.byType(TextFormField));
    final f = find.byType(TextFormField);
    await t.enterText(f.at(0), '4000');
    await t.enterText(f.at(1), '5000');
    await t.enterText(f.at(2), '2700');
    await t.ensureVisible(find.text('Continue'));
    await t.tap(find.text('Continue'));
    await _until(t, find.text('Door'));
    await t.ensureVisible(find.text('Continue'));
    await t.pump();
    await t.tap(find.text('Continue'));
    await _until(t, find.byType(ListTile)); // style options
    await t.tap(find.byType(ListTile).first);
    await _until(t, find.text('Furniture in the room'), seconds: 40);
    await t.tap(find.text('Add furniture'));
    await _until(t, find.byType(DraggableScrollableSheet), seconds: 5);
    await t.tap(find.text('Bedside table'));
    await _settle(t, seconds: 2);
    expect(find.byType(DraggableScrollableSheet), findsNothing);
    await _until(t, find.text('Bedside table'), seconds: 20); // the new item is in the list now
    await t.tap(find.text('Bedside table'));
    await _until(t, find.text('Remove furniture'), seconds: 5);
    await t.tap(find.text('90°'));
    await _settle(t, seconds: 2);
    await t.tapAt(const Offset(10, 100)); // close the sheet
    await _settle(t, seconds: 2);
    if (pause.isNotEmpty) await _settle(t, seconds: 25); // time to screenshot the 3D view
    expect(find.text('Furniture in the room'), findsOneWidget);
  }, timeout: const Timeout(Duration(minutes: 6)));
}
