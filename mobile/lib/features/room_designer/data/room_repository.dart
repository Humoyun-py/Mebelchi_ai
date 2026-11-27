import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../../shared/models/paged.dart';
import '../domain/room_models.dart';

class DownloadedFile {
  const DownloadedFile(this.name, this.bytes);
  final String name;
  final Uint8List bytes;
}

/// Thin client for `/rooms/` (the guided room designer). Every rule (limits, step order, placement, warnings) lives on the server.
class RoomRepository {
  RoomRepository(this._api);
  final ApiClient _api;
  Dio get _dio => _api.dio;

  Json _json(Response r) => asJson(r.data);

  Future<Paged<RoomBrief>> list({int page = 1}) => _api.guard(() async {
        final r = await _dio.get('rooms/', queryParameters: {'page': page});
        return Paged.fromJson(asJson(r.data), RoomBrief.fromJson);
      });

  Future<RoomFlow> start() => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.post('rooms/'))));
  Future<RoomFlow> get(int id) => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.get('rooms/$id/'))));
  Future<RoomFlow> answer(int id, String step, Object? value) => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.post('rooms/$id/answer/', data: {'step': step, 'value': value}))));
  Future<RoomFlow> back(int id) => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.post('rooms/$id/back/'))));
  Future<RoomFlow> finish(int id) => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.post('rooms/$id/finish/'))));
  Future<RoomFlow> addItem(int id, Json item) => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.post('rooms/$id/items/', data: item))));
  Future<RoomFlow> updateItem(int id, String itemId, Json patch) => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.patch('rooms/$id/items/$itemId/', data: patch))));
  Future<RoomFlow> removeItem(int id, String itemId) => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.delete('rooms/$id/items/$itemId/'))));
  Future<RoomFlow> updateSettings(int id, Json settings) => _api.guard(() async => RoomFlow.fromJson(_json(await _dio.patch('rooms/$id/settings/', data: settings))));
  Future<void> delete(int id) => _api.guard(() async {
        await _dio.delete('rooms/$id/');
      });

  Future<DownloadedFile> _download(String path, String fallback) => _api.guard(() async {
        final r = await _dio.get<List<int>>(path, options: Options(responseType: ResponseType.bytes));
        final cd = r.headers.value('content-disposition') ?? '';
        final m = RegExp(r'filename="([^"]+)"').firstMatch(cd);
        return DownloadedFile(m?.group(1) ?? fallback, Uint8List.fromList(r.data ?? const []));
      });

  /// The `.mebelchi` project file (portable format; not copy protection).
  Future<DownloadedFile> exportProject(int id) => _download('rooms/$id/export/', 'room.mebelchi');

  /// A standard GLB of the 3D room, used by the viewer and for sharing with other 3D apps.
  Future<DownloadedFile> exportGlb(int id) => _download('rooms/$id/export-glb/', 'room.glb');

  /// Stores a room photo in the gallery and returns its id. The photo is kept as a reference only; the server does not analyse it.
  Future<int> uploadPhoto(String path) => _api.guard(() async {
        final r = await _dio.post('gallery/', data: FormData.fromMap({'image': await MultipartFile.fromFile(path), 'source': 'upload'}));
        return (asJson(r.data)['id'] as num).toInt();
      });

  Future<RoomFlow> importProject(String path) => _api.guard(() async {
        final r = await _dio.post('rooms/import/', data: FormData.fromMap({'file': await MultipartFile.fromFile(path)}));
        return RoomFlow.fromJson(_json(r));
      });
}
