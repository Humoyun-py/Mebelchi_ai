import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../data/room_repository.dart';
import '../domain/room_models.dart';

final roomRepositoryProvider = Provider<RoomRepository>((ref) => RoomRepository(ref.watch(apiClientProvider)));

/// One open room design. Every action returns the new server state; errors are thrown to the screen so it can show them
/// next to the form while the previous state stays on screen.
class RoomController extends FamilyAsyncNotifier<RoomFlow, int> {
  RoomRepository get _repo => ref.read(roomRepositoryProvider);

  @override
  Future<RoomFlow> build(int arg) => _repo.get(arg);

  Future<void> _apply(Future<RoomFlow> Function() call) async {
    final next = await call();
    state = AsyncData(next);
  }

  Future<void> answer(String step, Object? value) => _apply(() => _repo.answer(arg, step, value));
  Future<void> back() => _apply(() => _repo.back(arg));
  Future<void> finish() => _apply(() => _repo.finish(arg));
  Future<void> addItem(Json item) => _apply(() => _repo.addItem(arg, item));
  Future<void> updateItem(String itemId, Json patch) => _apply(() => _repo.updateItem(arg, itemId, patch));
  Future<void> removeItem(String itemId) => _apply(() => _repo.removeItem(arg, itemId));
  Future<void> updateSettings(Json s) => _apply(() => _repo.updateSettings(arg, s));
  Future<void> reload() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() => _repo.get(arg));
  }
}

final roomControllerProvider = AsyncNotifierProvider.family<RoomController, RoomFlow, int>(RoomController.new);

final roomListProvider = FutureProvider.autoDispose((ref) => ref.watch(roomRepositoryProvider).list());
