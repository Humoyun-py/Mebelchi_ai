import '../../../core/network/api_client.dart';
import '../domain/furniture.dart';

class CatalogRepository {
  CatalogRepository(this._api);
  final ApiClient _api;

  /// The catalogue is a plain array (no pagination). Everybody sees approved items; the server filters the rest.
  Future<List<Furniture>> list({String? category, String? search}) => _api.guard(() async {
        final r = await _api.dio.get('furniture/templates/', queryParameters: {
          'category': ?category,
          if (search != null && search.trim().isNotEmpty) 'search': search.trim(),
          'is_available': true,
        });
        final data = r.data;
        final rows = data is List ? data : (data is Map ? (data['results'] as List? ?? const []) : const []);
        return rows.map((e) => Furniture.fromJson(Map<String, dynamic>.from(e as Map))).toList();
      });

  Future<Furniture> get(int id) => _api.guard(() async => Furniture.fromJson(Map<String, dynamic>.from((await _api.dio.get('furniture/templates/$id/')).data as Map)));
}
