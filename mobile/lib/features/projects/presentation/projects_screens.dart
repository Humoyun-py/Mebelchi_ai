import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/state_views.dart';
import '../domain/project.dart';
import 'projects_controller.dart';

class ProjectsScreen extends ConsumerStatefulWidget {
  const ProjectsScreen({super.key});
  @override
  ConsumerState<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends ConsumerState<ProjectsScreen> {
  String _status = 'active';
  String _search = '';
  Timer? _debounce;
  bool _loadingMore = false;

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  ProjectQuery get _q => (status: _status, search: _search);

  Future<void> _create() async {
    final created = await showModalBottomSheet<Project>(context: context, isScrollControlled: true, showDragHandle: true, builder: (_) => const _CreateSheet());
    if (created == null || !mounted) return;
    ref.invalidate(projectsProvider);
    context.push('/projects/${created.id}');
  }

  Future<void> _more() async {
    if (_loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      await ref.read(projectsProvider(_q).notifier).loadMore();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ref.read(stringsProvider).error(e))));
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final list = ref.watch(projectsProvider(_q));
    return Scaffold(
      appBar: AppBar(title: Text(s.t('pr.title'), style: const TextStyle(fontWeight: FontWeight.w700))),
      floatingActionButton: FloatingActionButton.extended(onPressed: _create, icon: const Icon(LucideIcons.plus), label: Text(s.t('pr.new')), backgroundColor: AppColors.primary, foregroundColor: Colors.white),
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: TextField(
            decoration: InputDecoration(hintText: s.t('cat.search'), prefixIcon: const Icon(LucideIcons.search, size: 20)),
            onChanged: (v) {
              _debounce?.cancel();
              _debounce = Timer(const Duration(milliseconds: 400), () => setState(() => _search = v));
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(children: [
            ChoiceChip(label: Text(s.t('pr.active')), selected: _status == 'active', onSelected: (_) => setState(() => _status = 'active')),
            const SizedBox(width: 8),
            ChoiceChip(label: Text(s.t('pr.archived')), selected: _status == 'archived', onSelected: (_) => setState(() => _status = 'archived')),
          ]),
        ),
        Expanded(
          child: list.when(
            loading: () => const LoadingView(),
            error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(projectsProvider)),
            data: (data) {
              if (data.items.isEmpty) return EmptyView(icon: LucideIcons.folderOpen, title: s.t(_status == 'archived' ? 'pr.empty.archived' : 'pr.empty.title'), message: _status == 'archived' ? null : s.t('pr.empty.body'));
              return RefreshIndicator(
                onRefresh: () async => ref.invalidate(projectsProvider),
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
                  itemCount: data.items.length + (data.nextPage != null ? 1 : 0),
                  separatorBuilder: (_, _) => const SizedBox(height: 8),
                  itemBuilder: (c, i) {
                    if (i == data.items.length) return Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: AppButton(label: s.t('pr.more'), outlined: true, loading: _loadingMore, onPressed: _more));
                    final p = data.items[i];
                    return Card(
                      child: ListTile(
                        leading: Icon(p.pinned ? LucideIcons.pin : LucideIcons.folder, color: p.pinned ? AppColors.accent : AppColors.textMuted),
                        title: Text(p.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Text('${s.t('cat.cat.${p.category}')} · ${s.f('pr.items', {'n': '${p.counts.total}'})}'),
                        trailing: const Icon(LucideIcons.chevronRight),
                        onTap: () => context.push('/projects/${p.id}'),
                      ),
                    );
                  },
                ),
              );
            },
          ),
        ),
      ]),
    );
  }
}

/// Name + type. The server validates (and applies the plan's project limit); its message is shown as is.
class _CreateSheet extends ConsumerStatefulWidget {
  const _CreateSheet({this.project});
  final Project? project;
  @override
  ConsumerState<_CreateSheet> createState() => _CreateSheetState();
}

class _CreateSheetState extends ConsumerState<_CreateSheet> {
  final _form = GlobalKey<FormState>();
  late final TextEditingController _name = TextEditingController(text: widget.project?.name ?? '');
  late final TextEditingController _desc = TextEditingController(text: widget.project?.description ?? '');
  late String _category = widget.project?.category ?? 'cabinet';
  bool _busy = false;
  AppException? _error;

  @override
  void dispose() {
    _name.dispose();
    _desc.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_busy || !_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final repo = ref.read(projectRepositoryProvider);
      final p = widget.project == null ? await repo.create(name: _name.text, category: _category, description: _desc.text) : await repo.update(widget.project!.id, name: _name.text, category: _category, description: _desc.text);
      if (mounted) Navigator.pop(context, p);
    } catch (e) {
      if (mounted) setState(() => _error = AppException.from(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final e = _error;
    final msg = e == null ? null : (e.kind == AppErrorKind.validation && e.fields.isNotEmpty ? e.fields.values.expand((x) => x).join('\n') : s.error(e));
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
      child: SingleChildScrollView(
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text(widget.project == null ? s.t('pr.new') : s.t('pr.edit'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 16),
            if (msg != null) ...[FormError(msg), const SizedBox(height: 12)],
            TextFormField(controller: _name, maxLength: 160, decoration: InputDecoration(labelText: s.t('pr.name')), validator: (v) => (v ?? '').trim().isEmpty ? s.t('auth.required') : null),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              initialValue: _category,
              decoration: InputDecoration(labelText: s.t('pr.category')),
              items: [for (final c in projectCategories) DropdownMenuItem(value: c, child: Text(s.t('cat.cat.$c')))],
              onChanged: (v) => setState(() => _category = v ?? _category),
            ),
            const SizedBox(height: 16),
            TextFormField(controller: _desc, maxLines: 3, decoration: InputDecoration(labelText: s.t('pr.description'))),
            const SizedBox(height: 16),
            AppButton(label: s.t('common.save'), loading: _busy, onPressed: _save),
          ]),
        ),
      ),
    );
  }
}

class ProjectDetailScreen extends ConsumerWidget {
  const ProjectDetailScreen({super.key, required this.id});
  final int id;

  Future<void> _run(BuildContext context, WidgetRef ref, Future<Object?> Function() action, {bool leave = false}) async {
    try {
      await action();
      ref.invalidate(projectProvider(id));
      ref.invalidate(projectsProvider);
      if (leave && context.mounted) context.pop();
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ref.read(stringsProvider).error(e))));
    }
  }

  Future<void> _delete(BuildContext context, WidgetRef ref) async {
    final s = ref.read(stringsProvider);
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(s.t('pr.delete.confirm')),
        content: Text(s.t('pr.delete.body')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: Text(s.t('common.cancel'))),
          TextButton(onPressed: () => Navigator.pop(c, true), child: Text(s.t('rd.delete'), style: const TextStyle(color: AppColors.danger))),
        ],
      ),
    );
    if (ok == true && context.mounted) await _run(context, ref, () => ref.read(projectRepositoryProvider).delete(id), leave: true);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final async = ref.watch(projectProvider(id));
    final repo = ref.read(projectRepositoryProvider);
    return Scaffold(
      appBar: AppBar(),
      body: async.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(projectProvider(id))),
        data: (p) => SafeArea(
          child: ListView(padding: const EdgeInsets.all(16), children: [
            Text(p.name, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text(s.t('cat.cat.${p.category}'), style: const TextStyle(color: AppColors.textMuted)),
            if (p.archived) Padding(padding: const EdgeInsets.only(top: 6), child: Text(s.t('pr.archived'), style: const TextStyle(color: AppColors.danger, fontWeight: FontWeight.w600))),
            if (p.description.isNotEmpty) ...[const SizedBox(height: 12), Text(p.description)],
            const SizedBox(height: 20),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Wrap(spacing: 24, runSpacing: 12, children: [
                  _Count(s.t('pr.count.calculations'), p.counts.calculations),
                  _Count(s.t('pr.count.cuttingLists'), p.counts.cuttingLists),
                  _Count(s.t('pr.count.designs'), p.counts.designs),
                  _Count(s.t('pr.count.images'), p.counts.images),
                  _Count(s.t('pr.count.files'), p.counts.files),
                ]),
              ),
            ),
            const SizedBox(height: 8),
            Text(s.t('pr.countsNote'), style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
            const SizedBox(height: 20),
            if (!p.archived) ...[
              AppButton(label: s.t('pr.calculate'), icon: LucideIcons.calculator, onPressed: () async {
                await context.push('/calculator?project=${p.id}');
                ref.invalidate(projectProvider(id));
              }),
              const SizedBox(height: 8),
            ],
            AppButton(
              label: s.t('pr.edit'),
              icon: LucideIcons.pencil,
              outlined: true,
              onPressed: () async {
                final changed = await showModalBottomSheet<Project>(context: context, isScrollControlled: true, showDragHandle: true, builder: (_) => _CreateSheet(project: p));
                if (changed != null) {
                  ref.invalidate(projectProvider(id));
                  ref.invalidate(projectsProvider);
                }
              },
            ),
            const SizedBox(height: 8),
            AppButton(label: p.pinned ? s.t('pr.unpin') : s.t('pr.pin'), icon: LucideIcons.pin, outlined: true, onPressed: () => _run(context, ref, () => repo.pin(id))),
            const SizedBox(height: 8),
            AppButton(label: p.archived ? s.t('pr.unarchive') : s.t('pr.archive'), icon: LucideIcons.archive, outlined: true, onPressed: () => _run(context, ref, () => p.archived ? repo.unarchive(id) : repo.archive(id))),
            const SizedBox(height: 8),
            TextButton.icon(onPressed: () => _delete(context, ref), icon: const Icon(LucideIcons.trash2, size: 20, color: AppColors.danger), label: Text(s.t('rd.delete'), style: const TextStyle(color: AppColors.danger))),
          ]),
        ),
      ),
    );
  }
}

class _Count extends StatelessWidget {
  const _Count(this.label, this.n);
  final String label;
  final int n;
  @override
  Widget build(BuildContext context) => SizedBox(
        width: 96,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('$n', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
          Text(label, style: const TextStyle(color: AppColors.textMuted, fontSize: 12)),
        ]),
      );
}
