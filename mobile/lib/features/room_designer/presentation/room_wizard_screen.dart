import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/state_views.dart';
import '../domain/room_models.dart';
import 'furnish_panel.dart';
import 'room_controller.dart';
import 'wizard_steps.dart';

/// The guided room designer. The server owns the order of steps and every rule; this screen only draws the current question.
/// It is a fixed-question assistant (no AI): see the note on the first step.
class RoomWizardScreen extends ConsumerStatefulWidget {
  const RoomWizardScreen({super.key, required this.roomId});
  final int roomId;
  @override
  ConsumerState<RoomWizardScreen> createState() => _RoomWizardScreenState();
}

class _RoomWizardScreenState extends ConsumerState<RoomWizardScreen> {
  bool _busy = false;
  AppException? _error;

  RoomController get _ctl => ref.read(roomControllerProvider(widget.roomId).notifier);

  Future<void> _submit(String step, Object? value) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _ctl.answer(step, value);
    } catch (e) {
      if (mounted) setState(() => _error = AppException.from(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _back() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _ctl.back();
    } catch (e) {
      if (mounted) setState(() => _error = AppException.from(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _errorText(AppException e) {
    final s = ref.read(stringsProvider);
    if (e.kind == AppErrorKind.validation || e.kind == AppErrorKind.notFound) {
      final all = e.fields.entries.map((x) => '${x.key.replaceAll('openings.', '#').replaceAll('value', '')} ${x.value.join(', ')}'.trim()).toList();
      if (all.isNotEmpty) return all.join('\n');
    }
    return s.error(e);
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final lang = ref.watch(languageProvider);
    final async = ref.watch(roomControllerProvider(widget.roomId));
    return async.when(
      loading: () => Scaffold(appBar: AppBar(), body: const LoadingView()),
      error: (e, _) => Scaffold(appBar: AppBar(), body: ErrorView(error: e, onRetry: () => ref.invalidate(roomControllerProvider(widget.roomId)))),
      data: (flow) {
        final q = flow.question;
        final step = flow.step;
        final furnish = flow.hasRoom && (step == 'furnish' || step == 'done');
        final canBack = q['can_back'] == true && flow.isActive;
        return Scaffold(
          appBar: AppBar(
            title: Text(furnish ? s.t('rd.title.room') : loc(q['title'], lang), style: const TextStyle(fontWeight: FontWeight.w700)),
            leading: IconButton(icon: const Icon(LucideIcons.arrowLeft), tooltip: s.t('common.close'), onPressed: () => context.canPop() ? context.pop() : context.go('/rooms')),
            bottom: furnish
                ? null
                : PreferredSize(preferredSize: const Size.fromHeight(4), child: LinearProgressIndicator(value: ((q['index'] as num?) ?? 1) / ((q['total'] as num?) ?? 1), minHeight: 4, backgroundColor: AppColors.border)),
            actions: [
              if (canBack) TextButton(onPressed: _busy ? null : _back, child: Text(s.t('rd.back'))),
            ],
          ),
          body: SafeArea(
            child: furnish
                ? FurnishPanel(flow: flow)
                : Center(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(AppSpacing.lg),
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 520),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                          Text(s.f('rd.stepOf', {'i': '${q['index'] ?? 1}', 'n': '${q['total'] ?? 1}'}), style: const TextStyle(color: AppColors.textMuted, fontSize: 13)),
                          const SizedBox(height: 4),
                          Text(loc(q['prompt'], lang), style: const TextStyle(fontSize: 16)),
                          if (step == 'goal') ...[const SizedBox(height: 8), Text(s.t('rd.guided.note'), style: const TextStyle(color: AppColors.textMuted, fontSize: 12))],
                          const SizedBox(height: AppSpacing.lg),
                          if (_error != null) ...[FormError(_errorText(_error!)), const SizedBox(height: 16)],
                          _stepBody(flow),
                        ]),
                      ),
                    ),
                  ),
          ),
        );
      },
    );
  }

  Widget _stepBody(RoomFlow flow) {
    final q = flow.question;
    final step = flow.step;
    Future<void> submit(Object? v) => _submit(step, v);
    switch (step) {
      case 'goal':
      case 'style':
        return ChoiceStep(key: ValueKey(step), question: q, onSubmit: submit, busy: _busy);
      case 'photo':
        return PhotoStep(key: ValueKey(step), onSubmit: submit, busy: _busy);
      case 'elements':
        return ElementsStep(key: ValueKey('${step}_${flow.updatedAt}'), question: q, onSubmit: submit, busy: _busy);
      case 'size':
        return SizeStep(key: ValueKey('${step}_${flow.updatedAt}'), question: q, onSubmit: submit, busy: _busy);
      case 'openings':
        return OpeningsStep(key: ValueKey('${step}_${flow.updatedAt}'), question: q, onSubmit: submit, busy: _busy);
      default:
        return const LoadingView();
    }
  }
}
