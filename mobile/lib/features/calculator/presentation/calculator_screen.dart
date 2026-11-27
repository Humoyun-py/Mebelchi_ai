import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/l10n/strings.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/state_views.dart';
import '../../projects/presentation/projects_controller.dart';
import '../data/calculator_repository.dart';
import '../domain/calculation.dart';

final calculatorRepositoryProvider = Provider<CalculatorRepository>((ref) => CalculatorRepository(ref.watch(apiClientProvider)));

String _n(double v) => v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);

/// Cabinet material calculator. Inputs go to the server's engine; the answer is shown unchanged
/// together with its assumptions and the "for professional review" notice.
class CalculatorScreen extends ConsumerStatefulWidget {
  const CalculatorScreen({super.key, this.projectId});
  final int? projectId;
  @override
  ConsumerState<CalculatorScreen> createState() => _CalculatorScreenState();
}

class _CalculatorScreenState extends ConsumerState<CalculatorScreen> {
  final _form = GlobalKey<FormState>();
  final _width = TextEditingController(text: '800');
  final _height = TextEditingController(text: '720');
  final _depth = TextEditingController(text: '560');
  final _thickness = TextEditingController(text: '18');
  final _material = TextEditingController(text: 'MDF');
  int _shelves = 1;
  int _doors = 2;
  int _drawers = 0;
  String _type = 'standard';
  String _handle = 'bar';

  CabinetInput? _input;
  CalcResult? _result;
  CuttingSummary? _cutting;
  bool _busy = false;
  AppException? _error;

  @override
  void dispose() {
    for (final c in [_width, _height, _depth, _thickness, _material]) {
      c.dispose();
    }
    super.dispose();
  }

  CabinetInput _read() => CabinetInput(
        width: double.parse(_width.text.replaceAll(',', '.')),
        height: double.parse(_height.text.replaceAll(',', '.')),
        depth: double.parse(_depth.text.replaceAll(',', '.')),
        thickness: double.parse(_thickness.text.replaceAll(',', '.')),
        shelves: _shelves,
        doors: _doors,
        drawers: _drawers,
        material: _material.text.trim().isEmpty ? 'MDF' : _material.text.trim(),
        cabinetType: _type,
        handleStyle: _handle,
      );

  Future<void> _run(Future<void> Function() job) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await job();
    } catch (e) {
      if (mounted) setState(() => _error = AppException.from(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _calculate() async {
    if (!_form.currentState!.validate()) return;
    final input = _read();
    await _run(() async {
      final r = await ref.read(calculatorRepositoryProvider).calculate(input);
      if (mounted) {
        setState(() {
          _input = input;
          _result = r;
          _cutting = null;
        });
      }
    });
  }

  Future<void> _save() async {
    final input = _input;
    if (input == null) return;
    final s = ref.read(stringsProvider);
    await _run(() async {
      final name = '${s.t('calc.title')} ${_n(input.width)}x${_n(input.height)}x${_n(input.depth)}';
      final r = await ref.read(calculatorRepositoryProvider).calculate(input, save: true, name: name, projectId: widget.projectId);
      ref.invalidate(projectsProvider);
      if (mounted) {
        setState(() => _result = r);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.t('calc.saved'))));
      }
    });
  }

  Future<void> _makeCuttingList() async {
    final input = _input;
    if (input == null) return;
    final s = ref.read(stringsProvider);
    await _run(() async {
      final name = '${s.t('calc.cuttingName')} ${_n(input.width)}x${_n(input.height)}x${_n(input.depth)}';
      final c = await ref.read(calculatorRepositoryProvider).cuttingList(input, name: name, projectId: widget.projectId);
      ref.invalidate(projectsProvider);
      if (mounted) setState(() => _cutting = c);
    });
  }

  String? _num(S s, String? v, {double min = 1}) {
    final x = double.tryParse((v ?? '').replaceAll(',', '.'));
    if (x == null) return s.t('calc.number');
    if (x < min) return s.t('calc.number');
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final result = _result;
    return Scaffold(
      appBar: AppBar(title: Text(s.t('calc.title'), style: const TextStyle(fontWeight: FontWeight.w700))),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: ListView(padding: const EdgeInsets.all(AppSpacing.md), children: [
              if (_error != null) ...[_ErrorBox(error: _error!), const SizedBox(height: AppSpacing.md)],
              if (result == null) ..._formFields(s) else ..._resultView(s, result),
            ]),
          ),
        ),
      ),
    );
  }

  List<Widget> _formFields(S s) => [
        Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            DropdownButtonFormField<String>(
              initialValue: _type,
              decoration: InputDecoration(labelText: s.t('calc.type')),
              items: [for (final t in cabinetTypes) DropdownMenuItem(value: t, child: Text(s.t('calc.type.$t')))],
              onChanged: (v) => setState(() => _type = v ?? _type),
            ),
            const SizedBox(height: AppSpacing.md),
            Row(children: [
              Expanded(child: _numField(_width, s.t('calc.width'), s)),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: _numField(_height, s.t('calc.height'), s)),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: _numField(_depth, s.t('calc.depth'), s)),
            ]),
            const SizedBox(height: AppSpacing.md),
            Row(children: [
              Expanded(child: _numField(_thickness, s.t('calc.thickness'), s)),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: TextFormField(controller: _material, maxLength: 20, decoration: InputDecoration(labelText: s.t('calc.material'), counterText: '')),
              ),
            ]),
            const SizedBox(height: AppSpacing.md),
            _Stepper(label: s.t('calc.shelves'), value: _shelves, max: 20, onChanged: (v) => setState(() => _shelves = v)),
            _Stepper(label: s.t('calc.doors'), value: _doors, max: 6, onChanged: (v) => setState(() => _doors = v)),
            _Stepper(label: s.t('calc.drawers'), value: _drawers, max: 10, onChanged: (v) => setState(() => _drawers = v)),
            const SizedBox(height: AppSpacing.sm),
            DropdownButtonFormField<String>(
              initialValue: _handle,
              decoration: InputDecoration(labelText: s.t('calc.handle')),
              items: [for (final h in handleStyles) DropdownMenuItem(value: h, child: Text(s.t('calc.handle.$h')))],
              onChanged: (v) => setState(() => _handle = v ?? _handle),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(s.t('calc.unitsNote'), style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
            const SizedBox(height: AppSpacing.lg),
            AppButton(label: s.t('calc.run'), icon: LucideIcons.calculator, loading: _busy, onPressed: _calculate),
          ]),
        ),
      ];

  Widget _numField(TextEditingController c, String label, S s) => TextFormField(
        controller: c,
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]'))],
        decoration: InputDecoration(labelText: label),
        validator: (v) => _num(s, v),
      );

  List<Widget> _resultView(S s, CalcResult r) => [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Wrap(spacing: 24, runSpacing: 12, children: [
              _Stat(s.t('calc.panels'), '${r.panelCount}'),
              _Stat(s.t('calc.area'), '${r.totalAreaM2.toStringAsFixed(2)} m²'),
              _Stat(s.t('calc.edge'), '${r.edgeBandingM.toStringAsFixed(1)} m'),
            ]),
          ),
        ),
        if (r.warnings.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          _Section(title: s.t('calc.warnings'), icon: LucideIcons.triangleAlert, color: AppColors.danger, lines: r.warnings),
        ],
        const SizedBox(height: AppSpacing.md),
        _Title(s.t('calc.materials')),
        for (final m in r.materials)
          ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            title: Text(m.label),
            subtitle: Text(s.f('calc.materialLine', {'n': '${m.parts}', 'a': m.areaM2.toStringAsFixed(2), 'w': m.withWasteM2.toStringAsFixed(2)})),
          ),
        const SizedBox(height: AppSpacing.sm),
        _Title(s.t('calc.parts')),
        for (final p in r.parts)
          ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            title: Text('${p.name} × ${p.quantity}'),
            subtitle: Text('${_n(p.width)} × ${_n(p.height)} × ${_n(p.thickness)} mm · ${p.material}'),
          ),
        const SizedBox(height: AppSpacing.sm),
        _Title(s.t('calc.hardware')),
        for (final h in r.hardware)
          ListTile(dense: true, contentPadding: EdgeInsets.zero, title: Text('${h.name} × ${h.quantity}'), subtitle: h.note.isEmpty ? null : Text(h.note)),
        const SizedBox(height: AppSpacing.sm),
        _Section(title: s.t('calc.assumptions'), icon: LucideIcons.info, color: AppColors.textMuted, lines: r.assumptions),
        const SizedBox(height: AppSpacing.md),
        Card(
          color: AppColors.surfaceAlt,
          child: Padding(padding: const EdgeInsets.all(AppSpacing.md), child: Text(s.t('calc.disclaimer'), style: const TextStyle(color: AppColors.textMuted))),
        ),
        if (_cutting != null) ...[
          const SizedBox(height: AppSpacing.md),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(s.t('calc.cuttingDone'), style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Text(s.f('calc.cuttingLine', {'n': '${_cutting!.sheetCount}', 'u': _cutting!.utilizationPct.toStringAsFixed(1)})),
                const SizedBox(height: 6),
                Text(s.t('calc.cuttingNote'), style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
              ]),
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.lg),
        AppButton(label: r.savedId == null ? s.t('calc.save') : s.t('calc.savedLabel'), icon: LucideIcons.save, loading: _busy, onPressed: r.savedId == null ? _save : null),
        const SizedBox(height: AppSpacing.sm),
        AppButton(label: s.t('calc.cutting'), icon: LucideIcons.scissors, outlined: true, loading: _busy, onPressed: _cutting == null ? _makeCuttingList : null),
        const SizedBox(height: AppSpacing.sm),
        AppButton(label: s.t('calc.edit'), icon: LucideIcons.pencil, outlined: true, onPressed: () => setState(() => _result = null)),
        if (widget.projectId != null) ...[
          const SizedBox(height: AppSpacing.sm),
          TextButton(onPressed: () => context.pop(), child: Text(s.t('calc.backToProject'))),
        ],
      ];
}

class _ErrorBox extends ConsumerWidget {
  const _ErrorBox({required this.error});
  final AppException error;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final msg = error.kind == AppErrorKind.validation && error.fields.isNotEmpty ? error.fields.entries.map((e) => '${e.key}: ${e.value.join(', ')}').join('\n') : s.error(error);
    return FormError(msg);
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({required this.label, required this.value, required this.max, required this.onChanged});
  final String label;
  final int value;
  final int max;
  final ValueChanged<int> onChanged;
  @override
  Widget build(BuildContext context) => Row(children: [
        Expanded(child: Text(label)),
        IconButton(tooltip: '−', onPressed: value > 0 ? () => onChanged(value - 1) : null, icon: const Icon(LucideIcons.minus)),
        SizedBox(width: 28, child: Text('$value', textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
        IconButton(tooltip: '+', onPressed: value < max ? () => onChanged(value + 1) : null, icon: const Icon(LucideIcons.plus)),
      ]);
}

class _Stat extends StatelessWidget {
  const _Stat(this.label, this.value);
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => SizedBox(
        width: 120,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700)),
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
        ]),
      );
}

class _Title extends StatelessWidget {
  const _Title(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.only(bottom: 4), child: Text(text, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)));
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.icon, required this.color, required this.lines});
  final String title;
  final IconData icon;
  final Color color;
  final List<String> lines;
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Icon(icon, size: 18, color: color), const SizedBox(width: 8), Text(title, style: TextStyle(fontWeight: FontWeight.w700, color: color))]),
        const SizedBox(height: 6),
        for (final l in lines) Padding(padding: const EdgeInsets.only(bottom: 4), child: Text('• $l', style: const TextStyle(fontSize: 13))),
      ]);
}
