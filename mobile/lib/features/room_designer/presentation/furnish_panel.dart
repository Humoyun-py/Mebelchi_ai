import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/state_views.dart';
import '../data/room_repository.dart';
import '../domain/room_models.dart';
import 'room_3d_view.dart';
import 'room_controller.dart';

const _swatches = ['#F8FAFC', '#E2E8F0', '#D8C3A5', '#C9A27A', '#94A3B8', '#0F172A', '#8B6F4E', '#A7F3D0'];
const floorMaterials = ['wood', 'laminate', 'tile', 'concrete', 'carpet'];

Color hexColor(String hex) => Color(int.parse('FF${hex.replaceFirst('#', '')}', radix: 16));

/// The last step: the 3D room, the furniture in it, colours/light, export and finish. Everything is saved on the server at once.
class FurnishPanel extends ConsumerStatefulWidget {
  const FurnishPanel({super.key, required this.flow});
  final RoomFlow flow;
  @override
  ConsumerState<FurnishPanel> createState() => _FurnishPanelState();
}

class _FurnishPanelState extends ConsumerState<FurnishPanel> {
  bool _busy = false;
  Object? _error;

  RoomController get _ctl => ref.read(roomControllerProvider(widget.flow.id).notifier);

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _share(Future<DownloadedFile> Function() load) => _run(() async {
        final f = await load();
        final dir = await getTemporaryDirectory();
        final file = File('${dir.path}/${f.name}');
        await file.writeAsBytes(f.bytes, flush: true);
        await SharePlus.instance.share(ShareParams(files: [XFile(file.path)], subject: f.name));
      });

  Future<void> _addFurniture() async {
    final s = ref.read(stringsProvider);
    final lang = ref.read(languageProvider);
    final catalog = asJsonList(widget.flow.question['catalog']);
    final picked = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (c) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.6,
        maxChildSize: 0.9,
        builder: (_, scroll) => ListView(controller: scroll, children: [
          Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 8), child: Text(s.t('rd.furnish.add'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
          for (final t in catalog)
            ListTile(
              title: Text(loc(t['label'], lang)),
              subtitle: Text(_dims(asJson(t['defaults']))),
              trailing: const Icon(LucideIcons.plus),
              onTap: () => Navigator.pop(c, t['slug'] as String),
            ),
        ]),
      ),
    );
    if (picked != null) await _run(() => _ctl.addItem({'template': picked}));
  }

  String _dims(Json d) => '${(d['width'] as num?)?.round() ?? '?'} x ${(d['depth'] as num?)?.round() ?? '?'} x ${(d['height'] as num?)?.round() ?? '?'} mm';

  Future<void> _editItem(Json item) async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (c) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(c).bottom),
        child: _ItemSheet(roomId: widget.flow.id, itemId: item['id'] as String),
      ),
    );
  }

  Widget _section(String title, Widget child) => Padding(
        padding: const EdgeInsets.only(top: 20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          const SizedBox(height: 8),
          child,
        ]),
      );

  Widget _colorRow(String label, String key, String? current) => Row(children: [
        SizedBox(width: 72, child: Text(label)),
        Expanded(
          child: Wrap(spacing: 8, runSpacing: 8, children: [
            for (final c in _swatches)
              Semantics(
                button: true,
                label: '$label $c',
                selected: current?.toLowerCase() == c.toLowerCase(),
                child: InkWell(
                  onTap: _busy ? null : () => _run(() => _ctl.updateSettings({key: c})),
                  customBorder: const CircleBorder(),
                  child: Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(color: hexColor(c), shape: BoxShape.circle, border: Border.all(color: current?.toLowerCase() == c.toLowerCase() ? AppColors.accent : AppColors.border, width: current?.toLowerCase() == c.toLowerCase() ? 3 : 1)),
                  ),
                ),
              ),
          ]),
        ),
      ]);

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final flow = widget.flow;
    final items = flow.items;
    final cfg = flow.config ?? {};
    final light = asJson(cfg['light']);
    final intensity = ((light['intensity'] as num?) ?? 1).toDouble().clamp(0.2, 2.0);
    final warm = light['warm'] == true;
    final floorMat = cfg['floor_material'] as String?;
    final readOnly = !flow.isActive;

    final panel = ListView(padding: const EdgeInsets.all(AppSpacing.md), children: [
      if (_error != null) ...[FormError(s.error(_error!)), const SizedBox(height: 12)],
      if (flow.warnings.isNotEmpty)
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: const Color(0xFFFFFBEB), borderRadius: BorderRadius.circular(12), border: Border.all(color: const Color(0xFFFDE68A))),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(s.t('rd.furnish.warnings'), style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            for (final w in flow.warnings) Padding(padding: const EdgeInsets.only(top: 2), child: Text('${w['item'] ?? ''} ${w['message'] ?? ''}'.trim())),
          ]),
        ),
      _section(
        s.t('rd.furnish.items'),
        Column(children: [
          if (items.isEmpty) Align(alignment: Alignment.centerLeft, child: Text(s.t('rd.furnish.noItems'), style: const TextStyle(color: AppColors.textMuted))),
          for (final it in items)
            Card(
              child: ListTile(
                title: Text('${it['name'] ?? it['template']}'),
                subtitle: Text(_dims(it)),
                trailing: const Icon(LucideIcons.chevronRight),
                onTap: readOnly ? null : () => _editItem(it),
              ),
            ),
          if (!readOnly) ...[const SizedBox(height: 8), AppButton(label: s.t('rd.furnish.add'), icon: LucideIcons.plus, outlined: true, onPressed: _busy ? null : _addFurniture)],
        ]),
      ),
      if (!readOnly)
        _section(
          s.t('rd.appearance'),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _colorRow(s.t('rd.wallColor'), 'wall', flow.colors['wall'] as String?),
            const SizedBox(height: 12),
            _colorRow(s.t('rd.floorColor'), 'floor', flow.colors['floor'] as String?),
            const SizedBox(height: 12),
            Wrap(spacing: 8, children: [
              for (final m in floorMaterials)
                ChoiceChip(label: Text(s.t('rd.floor.$m')), selected: floorMat == m, onSelected: _busy ? null : (_) => _run(() => _ctl.updateSettings({'floor_material': m}))),
            ]),
            const SizedBox(height: 12),
            Row(children: [
              const Icon(LucideIcons.sun, size: 20),
              Expanded(
                child: Slider(
                  value: intensity,
                  min: 0.2,
                  max: 2,
                  divisions: 18,
                  label: intensity.toStringAsFixed(1),
                  onChanged: _busy ? null : (v) => setState(() {}),
                  onChangeEnd: (v) => _run(() => _ctl.updateSettings({'light': {'intensity': double.parse(v.toStringAsFixed(1)), 'warm': warm}})),
                ),
              ),
            ]),
            SwitchListTile(contentPadding: EdgeInsets.zero, title: Text(s.t('rd.light.warm')), value: warm, onChanged: _busy ? null : (v) => _run(() => _ctl.updateSettings({'light': {'intensity': intensity, 'warm': v}}))),
          ]),
        ),
      _section(
        s.t('rd.export'),
        Column(children: [
          AppButton(label: s.t('rd.export.project'), icon: LucideIcons.share2, outlined: true, onPressed: _busy ? null : () => _share(() => ref.read(roomRepositoryProvider).exportProject(flow.id))),
          const SizedBox(height: 8),
          AppButton(label: s.t('rd.export.glb'), icon: LucideIcons.box, outlined: true, onPressed: _busy ? null : () => _share(() => ref.read(roomRepositoryProvider).exportGlb(flow.id))),
          const SizedBox(height: 6),
          Text(s.t('rd.export.note'), style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
        ]),
      ),
      if (!readOnly) ...[const SizedBox(height: 24), AppButton(label: s.t('rd.finish'), loading: _busy, onPressed: () => _run(_ctl.finish))],
      const SizedBox(height: 24),
    ]);

    return LayoutBuilder(builder: (context, c) {
      final view = Room3DView(roomId: flow.id, revision: flow.updatedAt);
      if (c.maxWidth >= 720) {
        return Row(children: [Expanded(flex: 5, child: Padding(padding: const EdgeInsets.all(12), child: view)), Expanded(flex: 4, child: panel)]);
      }
      return Column(children: [SizedBox(height: (c.maxHeight * 0.42).clamp(220, 420), child: Padding(padding: const EdgeInsets.fromLTRB(12, 0, 12, 0), child: view)), Expanded(child: panel)]);
    });
  }
}

class _ItemSheet extends ConsumerStatefulWidget {
  const _ItemSheet({required this.roomId, required this.itemId});
  final int roomId;
  final String itemId;
  @override
  ConsumerState<_ItemSheet> createState() => _ItemSheetState();
}

class _ItemSheetState extends ConsumerState<_ItemSheet> {
  bool _busy = false;
  Object? _error;
  String? _localError;
  final _w = TextEditingController();
  final _d = TextEditingController();
  final _h = TextEditingController();
  String? _loadedFor;

  @override
  void dispose() {
    _w.dispose();
    _d.dispose();
    _h.dispose();
    super.dispose();
  }

  Json? _item() {
    final flow = ref.read(roomControllerProvider(widget.roomId)).value;
    return flow?.items.where((i) => i['id'] == widget.itemId).firstOrNull;
  }

  Future<void> _patch(Json patch) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(roomControllerProvider(widget.roomId).notifier).updateItem(widget.itemId, patch);
      final it = _item();
      if (it != null) _fill(it, force: true);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _fill(Json it, {bool force = false}) {
    if (_loadedFor == null || force) {
      _w.text = '${(it['width'] as num).round()}';
      _d.text = '${(it['depth'] as num).round()}';
      _h.text = '${(it['height'] as num).round()}';
      _loadedFor = widget.itemId;
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final flow = ref.watch(roomControllerProvider(widget.roomId)).value;
    final it = flow?.items.where((i) => i['id'] == widget.itemId).firstOrNull;
    if (it == null) return const SizedBox(height: 120, child: LoadingView());
    _fill(it);
    final x = (it['x'] as num).toDouble();
    final z = (it['z'] as num).toDouble();
    final rot = (it['rot'] as num).round();
    Widget nudge(IconData icon, String label, Json Function() patch) => IconButton.outlined(tooltip: label, onPressed: _busy ? null : () => _patch(patch()), icon: Icon(icon, size: 20));
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${it['name'] ?? it['template']}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          if (_error != null || _localError != null) ...[const SizedBox(height: 8), FormError(_localError ?? s.error(_error!))],
          const SizedBox(height: 16),
          Text(s.t('rd.item.move'), style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            nudge(LucideIcons.arrowLeft, 'x-100', () => {'x': x - 100, 'z': z}),
            const SizedBox(width: 8),
            Column(children: [
              nudge(LucideIcons.arrowUp, 'z-100', () => {'x': x, 'z': z - 100}),
              const SizedBox(height: 8),
              nudge(LucideIcons.arrowDown, 'z+100', () => {'x': x, 'z': z + 100}),
            ]),
            const SizedBox(width: 8),
            nudge(LucideIcons.arrowRight, 'x+100', () => {'x': x + 100, 'z': z}),
          ]),
          const SizedBox(height: 16),
          Text(s.t('rd.item.rotate'), style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: [
            for (final r in const [0, 90, 180, 270]) ChoiceChip(label: Text('$r°'), selected: rot == r, onSelected: _busy ? null : (_) => _patch({'rot': r})),
          ]),
          const SizedBox(height: 16),
          Text('${s.t('rd.item.size')} (mm)', style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: TextField(controller: _w, keyboardType: TextInputType.number, decoration: InputDecoration(labelText: s.t('rd.width')))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _d, keyboardType: TextInputType.number, decoration: InputDecoration(labelText: s.t('rd.depth')))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: _h, keyboardType: TextInputType.number, decoration: InputDecoration(labelText: s.t('rd.height')))),
          ]),
          const SizedBox(height: 12),
          AppButton(
            label: s.t('common.save'),
            loading: _busy,
            onPressed: () {
              final w = int.tryParse(_w.text.trim());
              final d = int.tryParse(_d.text.trim());
              final h = int.tryParse(_h.text.trim());
              if (w == null || d == null || h == null) {
                setState(() => _localError = s.t('rd.wholeNumber'));
                return;
              }
              setState(() => _localError = null);
              _patch({'width': w, 'depth': d, 'height': h});
            },
          ),
          const SizedBox(height: 8),
          TextButton.icon(
            onPressed: _busy
                ? null
                : () async {
                    final nav = Navigator.of(context);
                    try {
                      await ref.read(roomControllerProvider(widget.roomId).notifier).removeItem(widget.itemId);
                      nav.pop();
                    } catch (e) {
                      if (mounted) setState(() => _error = e);
                    }
                  },
            icon: const Icon(LucideIcons.trash2, size: 20, color: AppColors.danger),
            label: Text(s.t('rd.item.remove'), style: const TextStyle(color: AppColors.danger)),
          ),
        ]),
      ),
    );
  }
}
