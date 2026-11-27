import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';

import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/state_views.dart';
import 'room_controller.dart';

String glbDataUri(List<int> bytes) => 'data:model/gltf-binary;base64,${base64Encode(bytes)}';

const _bg = Color(0xFFCBD5E1); // darker than the white walls, so the room outline stays visible

typedef _Key = ({int id, String rev});

/// The GLB is rebuilt by the server from the saved design, so the 3D view always shows real geometry; [rev] (the design's
/// `updated_at`) makes it reload after every change.
final roomGlbProvider = FutureProvider.autoDispose.family<String, _Key>((ref, key) async {
  final f = await ref.watch(roomRepositoryProvider).exportGlb(key.id);
  return glbDataUri(f.bytes);
});

/// Interactive 3D room (orbit and zoom). First-person walking is not available yet; the note under the view says so.
class Room3DView extends ConsumerWidget {
  const Room3DView({super.key, required this.roomId, required this.revision});
  final int roomId;
  final String revision;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final glb = ref.watch(roomGlbProvider((id: roomId, rev: revision)));
    return Column(children: [
      Expanded(
        child: ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Container(
            color: _bg,
            child: glb.when(
              loading: () => const LoadingView(),
              error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(roomGlbProvider)),
              data: (uri) => ModelViewer(
                key: ValueKey(revision),
                src: uri,
                alt: s.t('rd.view3d.alt'),
                cameraControls: true,
                autoRotate: false,
                backgroundColor: _bg,
                interactionPrompt: InteractionPrompt.none,
                shadowIntensity: 0.5,
              ),
            ),
          ),
        ),
      ),
      Padding(padding: const EdgeInsets.only(top: 6), child: Text(s.t('rd.view3d.note'), style: const TextStyle(color: AppColors.textMuted, fontSize: 12), textAlign: TextAlign.center)),
    ]);
  }
}
