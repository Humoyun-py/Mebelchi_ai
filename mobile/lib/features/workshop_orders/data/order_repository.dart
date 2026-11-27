import '../../../core/network/api_client.dart';
import '../../../shared/models/paged.dart';
import '../domain/order.dart';

class OrderRepository {
  OrderRepository(this._api);
  final ApiClient _api;

  Map<String, dynamic> _map(Object? v) => Map<String, dynamic>.from(v as Map);

  Future<Paged<WorkshopOrder>> list({String status = '', int page = 1}) => _api.guard(() async {
        final r = await _api.dio.get('orders/', queryParameters: {
          if (status.isNotEmpty) 'status': status,
          'page': page,
        });
        return Paged.fromJson(_map(r.data), WorkshopOrder.fromJson);
      });

  Future<WorkshopOrder> get(int id) => _api.guard(() async => WorkshopOrder.fromJson(_map((await _api.dio.get('orders/$id/')).data)));

  /// Moves an order to [status]. The server validates the move; a rejection needs [note] (the customer sees it).
  Future<WorkshopOrder> setStatus(int id, String status, {String note = ''}) => _api.guard(() async {
        final r = await _api.dio.patch('orders/$id/', data: {
          'status': status,
          if (note.trim().isNotEmpty) 'status_note': note.trim(),
        });
        return WorkshopOrder.fromJson(_map(r.data));
      });
}
