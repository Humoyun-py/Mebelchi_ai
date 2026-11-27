import '../../../core/network/api_client.dart';
import '../../../shared/models/paged.dart';
import '../domain/project.dart';

class ProjectRepository {
  ProjectRepository(this._api);
  final ApiClient _api;

  Map<String, dynamic> _map(Object? v) => Map<String, dynamic>.from(v as Map);

  Future<Paged<Project>> list({String status = 'active', String search = '', int page = 1}) => _api.guard(() async {
        final r = await _api.dio.get('projects/', queryParameters: {
          'status': status,
          if (search.trim().isNotEmpty) 'search': search.trim(),
          'ordering': '-pinned,-updated_at',
          'page': page,
        });
        return Paged.fromJson(_map(r.data), Project.fromJson);
      });

  Future<Project> get(int id) => _api.guard(() async => Project.fromJson(_map((await _api.dio.get('projects/$id/')).data)));
  Future<Project> create({required String name, required String category, String description = ''}) =>
      _api.guard(() async => Project.fromJson(_map((await _api.dio.post('projects/', data: {'name': name.trim(), 'category': category, 'description': description.trim()})).data)));
  Future<Project> update(int id, {String? name, String? category, String? description}) => _api.guard(() async {
        final body = <String, dynamic>{'name': ?name?.trim(), 'category': ?category, 'description': ?description?.trim()};
        return Project.fromJson(_map((await _api.dio.patch('projects/$id/', data: body)).data));
      });
  Future<void> delete(int id) => _api.guard(() async {
        await _api.dio.delete('projects/$id/');
      });
  Future<Project> pin(int id) => _api.guard(() async => Project.fromJson(_map((await _api.dio.post('projects/$id/pin/')).data)));
  Future<Project> archive(int id) => _api.guard(() async => Project.fromJson(_map((await _api.dio.post('projects/$id/archive/')).data)));
  Future<Project> unarchive(int id) => _api.guard(() async => Project.fromJson(_map((await _api.dio.post('projects/$id/unarchive/')).data)));
}
