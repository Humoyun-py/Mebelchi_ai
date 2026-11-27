import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../data/project_repository.dart';
import '../domain/project.dart';

final projectRepositoryProvider = Provider<ProjectRepository>((ref) => ProjectRepository(ref.watch(apiClientProvider)));

typedef ProjectQuery = ({String status, String search});

class ProjectList {
  const ProjectList(this.items, {required this.nextPage, required this.total});
  final List<Project> items;
  final int? nextPage; // null when everything is loaded
  final int total;
}

/// The user's projects for one filter, loaded page by page (the API pages by 24).
class ProjectsController extends AutoDisposeFamilyAsyncNotifier<ProjectList, ProjectQuery> {
  @override
  Future<ProjectList> build(ProjectQuery arg) async {
    final p = await ref.read(projectRepositoryProvider).list(status: arg.status, search: arg.search);
    return ProjectList(p.results, nextPage: p.hasMore ? 2 : null, total: p.count);
  }

  Future<void> loadMore() async {
    final cur = state.value;
    if (cur == null || cur.nextPage == null) return;
    final p = await ref.read(projectRepositoryProvider).list(status: arg.status, search: arg.search, page: cur.nextPage!);
    final ids = cur.items.map((e) => e.id).toSet();
    state = AsyncData(ProjectList([...cur.items, ...p.results.where((e) => !ids.contains(e.id))], nextPage: p.hasMore ? cur.nextPage! + 1 : null, total: p.count));
  }
}

final projectsProvider = AsyncNotifierProvider.autoDispose.family<ProjectsController, ProjectList, ProjectQuery>(ProjectsController.new);
final projectProvider = FutureProvider.autoDispose.family<Project, int>((ref, id) => ref.watch(projectRepositoryProvider).get(id));
