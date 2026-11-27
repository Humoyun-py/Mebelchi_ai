import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/room_designer/domain/room_models.dart';
import 'package:mebelchi_ai/features/room_designer/data/room_repository.dart';
import 'package:mebelchi_ai/features/room_designer/presentation/room_3d_view.dart';

import '../support/fake_adapter.dart';

const roomJson = {
  'id': 5,
  'status': 'active',
  'step': 'furnish',
  'answers': {},
  'question': {'step': 'furnish', 'title': {'en': 'Place', 'uz': 'Joylashtiring', 'ru': 'Расставьте'}, 'can_back': true},
  'design': 9,
  'room': {
    'config': {'room': {'width': 4000}, 'items': [{'id': 'a1', 'name': 'Bed', 'x': 1000, 'z': 900, 'rot': 0, 'width': 1600, 'depth': 2000, 'height': 500}], 'colors': {'wall': '#ffffff'}},
    'warnings': [{'code': 'door_zone', 'item': 'a1', 'message': 'blocks a door'}],
  },
  'updated_at': '2026-11-27T10:00:00Z',
};

void main() {
  late FakeAdapter adapter;
  late RoomRepository repo;

  setUp(() async {
    final st = MemoryTokenStorage();
    await st.write(const Tokens(access: 'a', refresh: 'r'));
    adapter = FakeAdapter((o) {
      if (o.path.endsWith('export-glb/')) return (status: 200, body: 'x');
      if (o.path == 'rooms/' && o.method == 'GET') return (status: 200, body: {'count': 1, 'next': null, 'previous': null, 'results': [{'id': 5, 'status': 'active', 'step': 'size', 'goal': 'kitchen', 'design': null, 'updated_at': 't'}]});
      return (status: 200, body: roomJson);
    });
    repo = RoomRepository(ApiClient(storage: st, baseUrl: 'http://x/api/v1', adapter: adapter));
  });

  test('loc picks the user language and falls back to English', () {
    expect(loc({'en': 'A', 'uz': 'B'}, 'uz'), 'B');
    expect(loc({'en': 'A'}, 'ru'), 'A');
    expect(loc('plain', 'uz'), 'plain');
    expect(loc(null, 'uz'), '');
  });

  test('RoomFlow parses the room, items and warnings', () {
    final f = RoomFlow.fromJson(Map<String, dynamic>.from(roomJson));
    expect(f.id, 5);
    expect(f.hasRoom, isTrue);
    expect(f.items.single['id'], 'a1');
    expect(f.warnings.single['message'], 'blocks a door');
    expect(f.colors['wall'], '#ffffff');
    expect(f.isActive, isTrue);
  });

  test('a flow before the 3D room exists has no config', () {
    final f = RoomFlow.fromJson({'id': 1, 'status': 'active', 'step': 'goal', 'question': {}, 'room': null, 'updated_at': ''});
    expect(f.hasRoom, isFalse);
    expect(f.items, isEmpty);
  });

  test('list uses the DRF envelope', () async {
    final page = await repo.list();
    expect(page.results.single.goal, 'kitchen');
    expect(adapter.log.single.uri.path, '/api/v1/rooms/');
  });

  test('answer, items and settings hit the documented routes with the documented bodies', () async {
    await repo.answer(5, 'size', {'width': 4000, 'length': 5000, 'height': 2700});
    expect(adapter.log.last.path, 'rooms/5/answer/');
    expect(adapter.log.last.data, {'step': 'size', 'value': {'width': 4000, 'length': 5000, 'height': 2700}});
    await repo.addItem(5, {'template': 'bedside'});
    expect(adapter.log.last.path, 'rooms/5/items/');
    await repo.updateItem(5, 'a1', {'rot': 90});
    expect(adapter.log.last.method, 'PATCH');
    expect(adapter.log.last.path, 'rooms/5/items/a1/');
    await repo.removeItem(5, 'a1');
    expect(adapter.log.last.method, 'DELETE');
    await repo.updateSettings(5, {'wall': '#ffffff'});
    expect(adapter.log.last.path, 'rooms/5/settings/');
    await repo.back(5);
    expect(adapter.log.last.path, 'rooms/5/back/');
  });

  test('GLB becomes a data URI for the viewer', () {
    expect(glbDataUri([0x67, 0x6c, 0x54, 0x46]), 'data:model/gltf-binary;base64,Z2xURg==');
  });
}
