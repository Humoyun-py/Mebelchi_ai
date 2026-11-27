import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/state_views.dart';
import '../domain/room_models.dart';
import 'room_controller.dart';

/// "My designs": the user's room designs, newest first. Start a new one or import a `.mebelchi` file.
class RoomsScreen extends ConsumerWidget {
  const RoomsScreen({super.key});

  Future<void> _new(BuildContext context, WidgetRef ref) async {
    try {
      final f = await ref.read(roomRepositoryProvider).start();
      ref.invalidate(roomListProvider);
      if (context.mounted) context.push('/rooms/${f.id}');
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ref.read(stringsProvider).error(e))));
    }
  }

  Future<void> _import(BuildContext context, WidgetRef ref) async {
    final s = ref.read(stringsProvider);
    final picked = await FilePicker.pickFile(type: FileType.any);
    final path = picked?.path;
    if (path == null) return;
    try {
      final f = await ref.read(roomRepositoryProvider).importProject(path);
      ref.invalidate(roomListProvider);
      if (!context.mounted) return;
      if (f.unknownModels.isNotEmpty) showSuccess(context, s.f('rd.import.unknown', {'n': '${f.unknownModels.length}'}));
      context.push('/rooms/${f.id}');
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.error(e))));
    }
  }

  Future<void> _delete(BuildContext context, WidgetRef ref, RoomBrief r) async {
    final s = ref.read(stringsProvider);
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(s.t('rd.delete.confirm')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: Text(s.t('common.cancel'))),
          TextButton(onPressed: () => Navigator.pop(c, true), child: Text(s.t('rd.delete'), style: const TextStyle(color: AppColors.danger))),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(roomRepositoryProvider).delete(r.id);
      ref.invalidate(roomListProvider);
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.error(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final list = ref.watch(roomListProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(s.t('rd.title'), style: const TextStyle(fontWeight: FontWeight.w700)),
        actions: [IconButton(tooltip: s.t('rd.import'), icon: const Icon(LucideIcons.download), onPressed: () => _import(context, ref))],
      ),
      floatingActionButton: FloatingActionButton.extended(onPressed: () => _new(context, ref), icon: const Icon(LucideIcons.plus), label: Text(s.t('rd.new')), backgroundColor: AppColors.primary, foregroundColor: Colors.white),
      body: list.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(roomListProvider)),
        data: (page) {
          if (page.results.isEmpty) return EmptyView(icon: LucideIcons.sofa, title: s.t('rd.empty.title'), message: s.t('rd.empty.body'));
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(roomListProvider),
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
              itemCount: page.results.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (c, i) {
                final r = page.results[i];
                final goalLabel = r.goal == null ? s.t('rd.untitled') : s.t('rd.goal.${r.goal}');
                final done = r.step == 'done' || r.status != 'active';
                return Card(
                  child: ListTile(
                    leading: Icon(done ? LucideIcons.check : LucideIcons.pencil, color: done ? AppColors.success : AppColors.textMuted),
                    title: Text('$goalLabel #${r.id}', style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text(done ? s.t('rd.status.done') : s.t('rd.status.inProgress')),
                    trailing: IconButton(tooltip: s.t('rd.delete'), icon: const Icon(LucideIcons.trash2, size: 20), onPressed: () => _delete(context, ref, r)),
                    onTap: () => context.push('/rooms/${r.id}'),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
