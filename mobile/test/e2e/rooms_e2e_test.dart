// Live-backend test of the room designer and the catalogue. Skipped unless MEBELCHI_E2E_URL is set.
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/authentication/data/auth_repository.dart';
import 'package:mebelchi_ai/features/authentication/domain/user.dart';
import 'package:mebelchi_ai/features/furniture_catalog/data/catalog_repository.dart';
import 'package:mebelchi_ai/features/projects/data/project_repository.dart';
import 'package:mebelchi_ai/features/room_designer/data/room_repository.dart';
import 'package:mebelchi_ai/features/room_designer/domain/room_models.dart';

void main() {
  final url = Platform.environment['MEBELCHI_E2E_URL'];
  final skip = url == null ? 'set MEBELCHI_E2E_URL to run against a live server' : false;

  test('catalogue, guided room design, items, settings, GLB and .mebelchi round trip', () async {
    final storage = MemoryTokenStorage();
    final api = ApiClient(storage: storage, baseUrl: url!);
    final auth = AuthRepository(api);
    final email = 'room${DateTime.now().microsecondsSinceEpoch}@example.com';
    final session = await auth.register(firstName: 'Room', lastName: 'Tester', email: email, password: 'Str0ng-pass-2026');
    await storage.write(session.tokens);
    await auth.setRole(UserRole.homeowner);

    // catalogue
    final catalog = CatalogRepository(api);
    final all = await catalog.list();
    expect(all, isNotEmpty);
    final detail = await catalog.get(all.first.id);
    expect(detail.width, isNotNull);
    expect(await catalog.list(category: 'kitchen'), everyElement(predicate<dynamic>((f) => f.category == 'kitchen')));

    final rooms = RoomRepository(api);
    var f = await rooms.start();
    expect(f.step, 'goal');
    f = await rooms.answer(f.id, 'goal', 'bedroom');
    expect(f.step, 'photo');
    f = await rooms.answer(f.id, 'photo', {'skip': true});
    expect(f.step, 'elements');

    // a bad answer comes back as field errors, state unchanged
    await expectLater(rooms.answer(f.id, 'elements', {'doors': 99, 'windows': 0, 'furniture': []}), throwsA(predicate((e) => e.toString().contains('validation'))));
    expect((await rooms.get(f.id)).step, 'elements');

    final options = asJsonList(asJsonList(f.question['fields']).firstWhere((x) => x['key'] == 'furniture')['options']);
    f = await rooms.answer(f.id, 'elements', {'doors': 1, 'windows': 1, 'furniture': [options.first['id']]});
    expect(f.step, 'size');
    f = await rooms.answer(f.id, 'size', {'width': 4000, 'length': 5000, 'height': 2700});
    expect(f.step, 'openings');
    f = await rooms.answer(f.id, 'openings', [
      {'type': 'door', 'wall': 'south', 'offset': 300, 'width': 900, 'height': 2100, 'sill': 0},
      {'type': 'window', 'wall': 'north', 'offset': 300, 'width': 1200, 'height': 1200, 'sill': 900},
    ]);
    expect(f.step, 'style');
    final style = asJsonList(f.question['options']).first['id'];
    f = await rooms.answer(f.id, 'style', style);
    expect(f.step, 'furnish');
    expect(f.hasRoom, isTrue);
    expect(f.items, isNotEmpty);

    // furnish
    final catalogOptions = asJsonList(f.question['catalog']);
    f = await rooms.addItem(f.id, {'template': catalogOptions.last['slug']});
    final added = f.items.last;
    f = await rooms.updateItem(f.id, added['id'] as String, {'rot': 90});
    expect(f.items.last['rot'], 90);
    f = await rooms.updateSettings(f.id, {'wall': '#D8C3A5', 'floor_material': 'tile', 'light': {'intensity': 1.4, 'warm': true}});
    expect(f.colors['wall'], '#D8C3A5');
    await expectLater(rooms.updateSettings(f.id, {'wall': 'not-a-colour'}), throwsA(predicate((e) => e.toString().contains('validation'))));
    final before = f.items.length;
    f = await rooms.removeItem(f.id, added['id'] as String);
    expect(f.items.length, before - 1);

    // exports
    final glb = await rooms.exportGlb(f.id);
    expect(String.fromCharCodes(glb.bytes.take(4)), 'glTF');
    final project = await rooms.exportProject(f.id);
    expect(project.name, endsWith('.mebelchi'));
    final tmp = File('${Directory.systemTemp.path}/e2e_${f.id}.mebelchi')..writeAsBytesSync(project.bytes);
    addTearDown(() => tmp.existsSync() ? tmp.deleteSync() : null);
    final imported = await rooms.importProject(tmp.path);
    expect(imported.id, isNot(f.id));
    expect(imported.items.length, f.items.length);

    // projects
    final projects = ProjectRepository(api);
    final proj = await projects.create(name: 'Kitchen for Ali', category: 'kitchen', description: 'measure on Monday');
    expect(proj.counts.total, 0);
    await projects.update(proj.id, name: 'Kitchen for Ali (v2)');
    expect((await projects.pin(proj.id)).pinned, isTrue);
    expect((await projects.list(search: 'Ali')).results.single.name, 'Kitchen for Ali (v2)');
    expect((await projects.archive(proj.id)).archived, isTrue);
    expect((await projects.list()).results, isEmpty);
    expect((await projects.list(status: 'archived')).results.single.id, proj.id);
    await projects.unarchive(proj.id);

    // another user cannot open it
    final other = ApiClient(storage: MemoryTokenStorage(), baseUrl: url);
    final s2 = await AuthRepository(other).register(firstName: 'Other', lastName: 'User', email: 'other${DateTime.now().microsecondsSinceEpoch}@example.com', password: 'Str0ng-pass-2026');
    final st2 = MemoryTokenStorage()..write(s2.tokens);
    final r2 = RoomRepository(ApiClient(storage: st2, baseUrl: url));
    await expectLater(r2.get(f.id), throwsA(predicate((e) => e.toString().contains('notFound'))));
    await expectLater(ProjectRepository(ApiClient(storage: st2, baseUrl: url)).get(proj.id), throwsA(predicate((e) => e.toString().contains('notFound'))));

    f = await rooms.finish(f.id);
    expect(f.step, 'done');
    await rooms.delete(imported.id);
    expect((await rooms.list()).results.any((r) => r.id == imported.id), isFalse);
    await projects.delete(proj.id);
    expect((await projects.list()).results, isEmpty);
    expect(Dio, isNotNull);
  }, skip: skip, timeout: const Timeout(Duration(minutes: 2)));
}
