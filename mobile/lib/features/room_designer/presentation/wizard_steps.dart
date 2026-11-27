import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../domain/room_models.dart';
import 'room_controller.dart';

typedef Submit = Future<void> Function(Object? value);

/// Choice step (room type, style): one tap answers.
class ChoiceStep extends ConsumerWidget {
  const ChoiceStep({super.key, required this.question, required this.onSubmit, required this.busy});
  final Json question;
  final Submit onSubmit;
  final bool busy;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(languageProvider);
    final options = asJsonList(question['options']);
    final current = question['value'];
    return Column(children: [
      for (final o in options)
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Card(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: BorderSide(color: current == o['id'] ? AppColors.accent : AppColors.border, width: current == o['id'] ? 2 : 1),
            ),
            child: ListTile(
              enabled: !busy,
              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              title: Text(loc(o['label'], lang), style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: o['text'] == null ? null : Text(loc(o['text'], lang)),
              trailing: const Icon(LucideIcons.chevronRight),
              onTap: () => onSubmit(o['id']),
            ),
          ),
        ),
    ]);
  }
}

/// Optional room photo. It is stored as a reference only (the server says so in the prompt); no sizes are read from it.
class PhotoStep extends ConsumerStatefulWidget {
  const PhotoStep({super.key, required this.onSubmit, required this.busy});
  final Submit onSubmit;
  final bool busy;
  @override
  ConsumerState<PhotoStep> createState() => _PhotoStepState();
}

class _PhotoStepState extends ConsumerState<PhotoStep> {
  bool _uploading = false;
  Object? _error;

  Future<void> _pick(ImageSource source) async {
    final file = await ImagePicker().pickImage(source: source, maxWidth: 2400, imageQuality: 85);
    if (file == null) return;
    setState(() {
      _uploading = true;
      _error = null;
    });
    try {
      final id = await ref.read(roomRepositoryProvider).uploadPhoto(file.path);
      await widget.onSubmit({'image_id': id});
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final disabled = widget.busy || _uploading;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (_error != null) Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(s.error(_error!), style: const TextStyle(color: AppColors.danger))),
      AppButton(label: s.t('rd.photo.camera'), icon: LucideIcons.camera, loading: _uploading, onPressed: disabled ? null : () => _pick(ImageSource.camera)),
      const SizedBox(height: 12),
      AppButton(label: s.t('rd.photo.gallery'), icon: LucideIcons.image, outlined: true, onPressed: disabled ? null : () => _pick(ImageSource.gallery)),
      const SizedBox(height: 12),
      TextButton(onPressed: disabled ? null : () => widget.onSubmit({'skip': true}), child: Text(s.t('rd.photo.skip'))),
    ]);
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({required this.label, required this.value, required this.min, required this.max, required this.onChanged});
  final String label;
  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) => Row(children: [
        Expanded(child: Text(label, style: const TextStyle(fontWeight: FontWeight.w600))),
        IconButton.outlined(tooltip: '-', onPressed: value > min ? () => onChanged(value - 1) : null, icon: const Icon(LucideIcons.minus, size: 18)),
        SizedBox(width: 40, child: Center(child: Text('$value', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)))),
        IconButton.outlined(tooltip: '+', onPressed: value < max ? () => onChanged(value + 1) : null, icon: const Icon(LucideIcons.plus, size: 18)),
      ]);
}

/// Doors, windows and the furniture the user wants. The server decides which furniture is allowed for the room type.
class ElementsStep extends ConsumerStatefulWidget {
  const ElementsStep({super.key, required this.question, required this.onSubmit, required this.busy});
  final Json question;
  final Submit onSubmit;
  final bool busy;
  @override
  ConsumerState<ElementsStep> createState() => _ElementsStepState();
}

class _ElementsStepState extends ConsumerState<ElementsStep> {
  late int doors;
  late int windows;
  late Set<String> furniture;

  Json _field(String key) => asJsonList(widget.question['fields']).firstWhere((f) => f['key'] == key, orElse: () => <String, dynamic>{});

  @override
  void initState() {
    super.initState();
    final v = asJson(widget.question['value']);
    doors = (v['doors'] as num?)?.toInt() ?? (_field('doors')['default'] as num?)?.toInt() ?? 1;
    windows = (v['windows'] as num?)?.toInt() ?? (_field('windows')['default'] as num?)?.toInt() ?? 1;
    furniture = ((v['furniture'] as List?) ?? const []).map((e) => e.toString()).toSet();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final lang = ref.watch(languageProvider);
    final d = _field('doors');
    final w = _field('windows');
    final f = _field('furniture');
    final max = (f['max'] as num?)?.toInt() ?? 20;
    final options = asJsonList(f['options']);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _Stepper(label: loc(d['label'], lang), value: doors, min: (d['min'] as num?)?.toInt() ?? 0, max: (d['max'] as num?)?.toInt() ?? 5, onChanged: (v) => setState(() => doors = v)),
      const SizedBox(height: 8),
      _Stepper(label: loc(w['label'], lang), value: windows, min: (w['min'] as num?)?.toInt() ?? 0, max: (w['max'] as num?)?.toInt() ?? 8, onChanged: (v) => setState(() => windows = v)),
      const SizedBox(height: 20),
      Text('${loc(f['label'], lang)} (${furniture.length}/$max)', style: const TextStyle(fontWeight: FontWeight.w600)),
      const SizedBox(height: 8),
      Wrap(spacing: 8, runSpacing: 8, children: [
        for (final o in options)
          FilterChip(
            label: Text(loc(o['label'], lang)),
            selected: furniture.contains(o['id']),
            onSelected: widget.busy
                ? null
                : (on) => setState(() {
                      if (on && furniture.length < max) furniture.add(o['id'] as String);
                      if (!on) furniture.remove(o['id']);
                    }),
          ),
      ]),
      const SizedBox(height: 24),
      AppButton(label: s.t('common.continue'), loading: widget.busy, onPressed: () => widget.onSubmit({'doors': doors, 'windows': windows, 'furniture': furniture.toList()})),
    ]);
  }
}

/// Room size in millimetres. The limits come from the server and are checked here only to give instant feedback.
class SizeStep extends ConsumerStatefulWidget {
  const SizeStep({super.key, required this.question, required this.onSubmit, required this.busy});
  final Json question;
  final Submit onSubmit;
  final bool busy;
  @override
  ConsumerState<SizeStep> createState() => _SizeStepState();
}

class _SizeStepState extends ConsumerState<SizeStep> {
  final _form = GlobalKey<FormState>();
  final Map<String, TextEditingController> _c = {};

  @override
  void initState() {
    super.initState();
    final v = asJson(widget.question['value']);
    for (final f in asJsonList(widget.question['fields'])) {
      final k = f['key'] as String;
      _c[k] = TextEditingController(text: v[k] == null ? '' : '${(v[k] as num).round()}');
    }
  }

  @override
  void dispose() {
    for (final c in _c.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _go() {
    if (!_form.currentState!.validate()) return;
    widget.onSubmit({for (final e in _c.entries) e.key: int.parse(e.value.text.trim())});
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final lang = ref.watch(languageProvider);
    final fields = asJsonList(widget.question['fields']);
    return Form(
      key: _form,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (final f in fields) ...[
          TextFormField(
            controller: _c[f['key']],
            keyboardType: TextInputType.number,
            textInputAction: TextInputAction.next,
            enabled: !widget.busy,
            decoration: InputDecoration(labelText: '${loc(f['label'], lang)} (mm)', helperText: s.f('rd.range', {'lo': '${(f['min'] as num).round()}', 'hi': '${(f['max'] as num).round()}'})),
            validator: (v) {
              final n = int.tryParse((v ?? '').trim());
              if (n == null) return s.t('rd.wholeNumber');
              if (n < (f['min'] as num) || n > (f['max'] as num)) return s.f('rd.range', {'lo': '${(f['min'] as num).round()}', 'hi': '${(f['max'] as num).round()}'});
              return null;
            },
          ),
          const SizedBox(height: 16),
        ],
        const SizedBox(height: 8),
        AppButton(label: s.t('common.continue'), loading: widget.busy, onPressed: _go),
      ]),
    );
  }
}

class _OpeningDraft {
  _OpeningDraft({required this.type, required this.wall, required this.offset, required this.width, required this.height, required this.sill});
  final String type;
  String wall;
  int offset;
  int width;
  int height;
  int sill;
  Json toJson() => {'type': type, 'wall': wall, 'offset': offset, 'width': width, 'height': height, 'sill': type == 'door' ? 0 : sill};
}

/// One card per required door/window: wall, distance from the wall start and size.
class OpeningsStep extends ConsumerStatefulWidget {
  const OpeningsStep({super.key, required this.question, required this.onSubmit, required this.busy});
  final Json question;
  final Submit onSubmit;
  final bool busy;
  @override
  ConsumerState<OpeningsStep> createState() => _OpeningsStepState();
}

class _OpeningsStepState extends ConsumerState<OpeningsStep> {
  final _form = GlobalKey<FormState>();
  late final List<_OpeningDraft> _drafts;
  late final List<List<TextEditingController>> _ctrls;

  int _clamp(num v, List? range) => range == null || range.length < 2 ? v.round() : v.clamp(range[0] as num, range[1] as num).round();

  @override
  void initState() {
    super.initState();
    final limits = asJson(widget.question['limits']);
    final req = asJson(widget.question['required']);
    final door = asJson(limits['door']);
    final win = asJson(limits['window']);
    final saved = asJsonList(widget.question['value']);
    _drafts = saved.isNotEmpty
        ? [for (final o in saved) _OpeningDraft(type: o['type'] as String, wall: o['wall'] as String, offset: (o['offset'] as num).round(), width: (o['width'] as num).round(), height: (o['height'] as num).round(), sill: ((o['sill'] ?? 0) as num).round())]
        : [
            for (var i = 0; i < ((req['doors'] as num?) ?? 0); i++) _OpeningDraft(type: 'door', wall: 'south', offset: 300 + i * 1200, width: _clamp(900, door['width'] as List?), height: _clamp(2100, door['height'] as List?), sill: 0),
            for (var i = 0; i < ((req['windows'] as num?) ?? 0); i++) _OpeningDraft(type: 'window', wall: 'north', offset: 300 + i * 1600, width: _clamp(1200, win['width'] as List?), height: _clamp(1200, win['height'] as List?), sill: _clamp(900, win['sill'] as List?)),
          ];
    _ctrls = [
      for (final d in _drafts) [for (final v in [d.offset, d.width, d.height, d.sill]) TextEditingController(text: '$v')]
    ];
  }

  @override
  void dispose() {
    for (final l in _ctrls) {
      for (final c in l) {
        c.dispose();
      }
    }
    super.dispose();
  }

  void _go() {
    if (!_form.currentState!.validate()) return;
    for (var i = 0; i < _drafts.length; i++) {
      final c = _ctrls[i];
      _drafts[i]
        ..offset = int.parse(c[0].text.trim())
        ..width = int.parse(c[1].text.trim())
        ..height = int.parse(c[2].text.trim())
        ..sill = int.tryParse(c[3].text.trim()) ?? 0;
    }
    widget.onSubmit([for (final d in _drafts) d.toJson()]);
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final lang = ref.watch(languageProvider);
    final walls = asJsonList(widget.question['walls']);
    final lengths = asJson(widget.question['wall_lengths']);
    String? intCheck(String? v) => int.tryParse((v ?? '').trim()) == null ? s.t('rd.wholeNumber') : null;
    return Form(
      key: _form,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (var i = 0; i < _drafts.length; i++) ...[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Row(children: [
                  Icon(_drafts[i].type == 'door' ? LucideIcons.doorOpen : LucideIcons.squareDashed, size: 20),
                  const SizedBox(width: 8),
                  Text(_drafts[i].type == 'door' ? s.t('rd.opening.door') : s.t('rd.opening.window'), style: const TextStyle(fontWeight: FontWeight.w700)),
                ]),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _drafts[i].wall,
                  decoration: InputDecoration(labelText: s.t('rd.wall')),
                  items: [for (final w in walls) DropdownMenuItem(value: w['id'] as String, child: Text('${loc(w['label'], lang)}${lengths[w['id']] == null ? '' : ' (${(lengths[w['id']] as num).round()} mm)'}'))],
                  onChanged: widget.busy ? null : (v) => setState(() => _drafts[i].wall = v ?? _drafts[i].wall),
                ),
                const SizedBox(height: 12),
                TextFormField(controller: _ctrls[i][0], keyboardType: TextInputType.number, decoration: InputDecoration(labelText: '${s.t('rd.offset')} (mm)'), validator: intCheck),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(child: TextFormField(controller: _ctrls[i][1], keyboardType: TextInputType.number, decoration: InputDecoration(labelText: '${s.t('rd.width')} (mm)'), validator: intCheck)),
                  const SizedBox(width: 12),
                  Expanded(child: TextFormField(controller: _ctrls[i][2], keyboardType: TextInputType.number, decoration: InputDecoration(labelText: '${s.t('rd.height')} (mm)'), validator: intCheck)),
                ]),
                if (_drafts[i].type == 'window') ...[
                  const SizedBox(height: 12),
                  TextFormField(controller: _ctrls[i][3], keyboardType: TextInputType.number, decoration: InputDecoration(labelText: '${s.t('rd.sill')} (mm)'), validator: intCheck),
                ],
              ]),
            ),
          ),
          const SizedBox(height: 12),
        ],
        AppButton(label: s.t('common.continue'), loading: widget.busy, onPressed: _go),
      ]),
    );
  }
}
