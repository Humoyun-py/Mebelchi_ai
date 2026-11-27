import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/providers.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/projects/data/project_repository.dart';
import 'package:mebelchi_ai/features/projects/domain/project.dart';
import 'package:mebelchi_ai/features/projects/presentation/projects_controller.dart';

import '../support/fake_adapter.dart';

Map<String, dynamic> row(int id, {String status = 'active'}) => {'id': id, 'name': 'P$id', 'description': '', 'category': 'kitchen', 'status': status, 'pinned': id == 1, 'counts': {'calculations': 2, 'cutting_lists': 1, 'designs': 0, 'images': 3, 'files': 0}, 'updated_at': 't'};

void main() {
  test('Project parses counts and flags', () {
    final p = Project.fromJson(row(1));
    expect(p.pinned, isTrue);
    expect(p.counts.total, 6);
    expect(Project.fromJson(row(2, status: 'archived')).archived, isTrue);
    expect(Project.fromJson({'id': 3}).counts.total, 0);
  });

  test('repository uses the documented routes and bodies', () async {
    final st = MemoryTokenStorage();
    final a = FakeAdapter((o) => (status: 200, body: o.path == 'projects/' && o.method == 'GET' ? {'count': 1, 'next': null, 'previous': null, 'results': [row(1)]} : row(1)));
    final repo = ProjectRepository(ApiClient(storage: st, baseUrl: 'http://x/api/v1', adapter: a));
    await repo.list(status: 'archived', search: ' kit ');
    expect(a.log.last.queryParameters, {'status': 'archived', 'search': 'kit', 'ordering': '-pinned,-updated_at', 'page': 1});
    await repo.create(name: ' Kitchen ', category: 'kitchen', description: ' d ');
    expect(a.log.last.data, {'name': 'Kitchen', 'category': 'kitchen', 'description': 'd'});
    await repo.update(1, name: 'New');
    expect(a.log.last.method, 'PATCH');
    expect(a.log.last.data, {'name': 'New'});
    await repo.pin(1);
    await repo.archive(1);
    await repo.unarchive(1);
    expect(a.log.map((o) => o.path).toList().sublist(3), ['projects/1/pin/', 'projects/1/archive/', 'projects/1/unarchive/']);
    await repo.delete(1);
    expect(a.log.last.method, 'DELETE');
  });

  test('the list loads further pages without duplicating items', () async {
    final st = MemoryTokenStorage();
    final a = FakeAdapter((o) {
      final page = o.queryParameters['page'];
      return page == 1
          ? (status: 200, body: {'count': 3, 'next': 'x', 'previous': null, 'results': [row(1), row(2)]})
          : (status: 200, body: {'count': 3, 'next': null, 'previous': 'x', 'results': [row(2), row(3)]});
    });
    final c = ProviderContainer(overrides: [apiClientProvider.overrideWith((ref) => ApiClient(storage: st, baseUrl: 'http://x/api/v1', adapter: a))]);
    addTearDown(c.dispose);
    const q = (status: 'active', search: '');
    c.listen(projectsProvider(q), (_, _) {});
    final first = await c.read(projectsProvider(q).future);
    expect(first.items.length, 2);
    expect(first.nextPage, 2);
    await c.read(projectsProvider(q).notifier).loadMore();
    final all = c.read(projectsProvider(q)).value!;
    expect(all.items.map((e) => e.id), [1, 2, 3]);
    expect(all.nextPage, isNull);
  });
}
