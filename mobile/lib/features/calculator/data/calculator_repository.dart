import '../../../core/network/api_client.dart';
import '../domain/calculation.dart';

class CalculatorRepository {
  CalculatorRepository(this._api);
  final ApiClient _api;

  Map<String, dynamic> _map(Object? v) => Map<String, dynamic>.from(v as Map);

  /// Stateless calculation; with [save] the server also stores it (optionally inside [projectId]).
  Future<CalcResult> calculate(CabinetInput input, {bool save = false, String? name, int? projectId}) => _api.guard(() async {
        final body = <String, dynamic>{
          ...input.toJson(),
          if (save) 'save': true,
          if (save && name != null && name.trim().isNotEmpty) 'name': name.trim(),
          if (save) 'project': ?projectId,
        };
        final r = await _api.dio.post('calculations/material/', data: body);
        return CalcResult.fromJson(_map(r.data));
      });

  /// Creates a cutting list from the same inputs and runs the optimiser on it.
  Future<CuttingSummary> cuttingList(CabinetInput input, {String? name, int? projectId}) => _api.guard(() async {
        final created = _map((await _api.dio.post('cutting-lists/from-calculation/', data: {
          ...input.toJson(),
          if (name != null && name.trim().isNotEmpty) 'name': name.trim(),
          'project': ?projectId,
        }))
            .data);
        final id = (created['id'] as num).toInt();
        final run = _map((await _api.dio.post('cutting-lists/$id/optimize/', data: {'allow_rotation': true})).data);
        return CuttingSummary(listId: id, sheetCount: (run['sheet_count'] as num?)?.toInt() ?? 0, utilizationPct: (run['utilization_pct'] as num?)?.toDouble() ?? 0);
      });
}
