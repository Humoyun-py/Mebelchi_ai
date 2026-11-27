import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/config/env.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/state_views.dart';
import '../../room_designer/presentation/room_controller.dart';
import '../data/catalog_repository.dart';
import '../domain/furniture.dart';

final catalogRepositoryProvider = Provider<CatalogRepository>((ref) => CatalogRepository(ref.watch(apiClientProvider)));

typedef CatalogQuery = ({String? category, String search});

final catalogProvider = FutureProvider.autoDispose.family<List<Furniture>, CatalogQuery>((ref, q) => ref.watch(catalogRepositoryProvider).list(category: q.category, search: q.search));
final furnitureProvider = FutureProvider.autoDispose.family<Furniture, int>((ref, id) => ref.watch(catalogRepositoryProvider).get(id));

const catalogCategories = ['kitchen', 'wardrobe', 'tv_unit', 'bedroom', 'living', 'office'];

class _Thumb extends StatelessWidget {
  const _Thumb(this.item, {this.size = 72});
  final Furniture item;
  final double size;
  @override
  Widget build(BuildContext context) {
    final front = item.images.where((i) => i.view == 'front').firstOrNull ?? item.images.firstOrNull;
    final fallback = Container(width: size, height: size, color: AppColors.surfaceAlt, child: const Icon(LucideIcons.sofa, color: AppColors.textMuted));
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: front == null
          ? fallback
          : CachedNetworkImage(imageUrl: Env.resolveUrl(front.url), width: size, height: size, fit: BoxFit.cover, cacheKey: 'furn-${item.id}-${front.view}', errorWidget: (_, _, _) => fallback, placeholder: (_, _) => fallback),
    );
  }
}

class CatalogScreen extends ConsumerStatefulWidget {
  const CatalogScreen({super.key});
  @override
  ConsumerState<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends ConsumerState<CatalogScreen> {
  String? _category;
  String _search = '';
  Timer? _debounce;

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final list = ref.watch(catalogProvider((category: _category, search: _search)));
    return Scaffold(
      appBar: AppBar(title: Text(s.t('cat.title'), style: const TextStyle(fontWeight: FontWeight.w700))),
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
        SizedBox(
          height: 44,
          child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 16), children: [
            Padding(padding: const EdgeInsets.only(right: 8), child: ChoiceChip(label: Text(s.t('cat.all')), selected: _category == null, onSelected: (_) => setState(() => _category = null))),
            for (final c in catalogCategories) Padding(padding: const EdgeInsets.only(right: 8), child: ChoiceChip(label: Text(s.t('cat.cat.$c')), selected: _category == c, onSelected: (_) => setState(() => _category = c))),
          ]),
        ),
        Expanded(
          child: list.when(
            loading: () => const LoadingView(),
            error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(catalogProvider)),
            data: (items) {
              if (items.isEmpty) return EmptyView(icon: LucideIcons.packageOpen, title: s.t('cat.empty.title'), message: s.t('cat.empty.body'));
              return RefreshIndicator(
                onRefresh: () async => ref.invalidate(catalogProvider),
                child: ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: items.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 8),
                  itemBuilder: (c, i) {
                    final it = items[i];
                    return Card(
                      child: ListTile(
                        contentPadding: const EdgeInsets.all(10),
                        leading: _Thumb(it),
                        title: Text(it.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Text([it.dimensions, if (it.workshopName != null) it.workshopName!].join('\n')),
                        isThreeLine: it.workshopName != null,
                        trailing: Text(it.price == null ? s.t('cat.noPrice') : '${it.price} ${it.currency}', style: const TextStyle(fontWeight: FontWeight.w600)),
                        onTap: () => context.push('/catalog/${it.id}'),
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

class FurnitureDetailScreen extends ConsumerWidget {
  const FurnitureDetailScreen({super.key, required this.id});
  final int id;

  Future<void> _addToRoom(BuildContext context, WidgetRef ref, Furniture item) async {
    final s = ref.read(stringsProvider);
    final rooms = await ref.read(roomRepositoryProvider).list();
    final open = rooms.results.where((r) => r.status == 'active' && r.step == 'furnish').toList();
    if (!context.mounted) return;
    if (open.isEmpty) {
      showSuccess(context, s.t('cat.addToRoom.none'));
      return;
    }
    final id = await showModalBottomSheet<int>(
      context: context,
      showDragHandle: true,
      builder: (c) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 8), child: Text(s.t('cat.addToRoom'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
          for (final r in open) ListTile(title: Text('${r.goal == null ? s.t('rd.untitled') : s.t('rd.goal.${r.goal}')} #${r.id}'), onTap: () => Navigator.pop(c, r.id)),
        ]),
      ),
    );
    if (id == null) return;
    try {
      final flow = await ref.read(roomRepositoryProvider).addItem(id, {'template': item.slug});
      ref.invalidate(roomControllerProvider(id));
      if (context.mounted) {
        final msg = flow.warnings.isEmpty ? s.t('cat.addToRoom.done') : flow.warnings.last['message']?.toString() ?? s.t('cat.addToRoom.done');
        showSuccess(context, msg);
      }
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s.error(e))));
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final async = ref.watch(furnitureProvider(id));
    return Scaffold(
      appBar: AppBar(),
      body: async.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(furnitureProvider(id))),
        data: (it) => SafeArea(
          child: ListView(padding: const EdgeInsets.all(16), children: [
            if (it.images.isNotEmpty)
              SizedBox(
                height: 220,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: it.images.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 8),
                  itemBuilder: (_, i) => Stack(children: [
                    ClipRRect(borderRadius: BorderRadius.circular(16), child: CachedNetworkImage(imageUrl: Env.resolveUrl(it.images[i].url), height: 220, width: 260, fit: BoxFit.cover, cacheKey: 'furn-${it.id}-${it.images[i].view}')),
                    Positioned(left: 8, bottom: 8, child: Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2), decoration: BoxDecoration(color: AppColors.primary.withValues(alpha: 0.8), borderRadius: BorderRadius.circular(8)), child: Text(s.t('cat.view.${it.images[i].view}'), style: const TextStyle(color: Colors.white, fontSize: 12)))),
                  ]),
                ),
              )
            else
              Center(child: _Thumb(it, size: 160)),
            const SizedBox(height: 16),
            Text(it.name, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Text(it.price == null ? s.t('cat.noPrice') : '${it.price} ${it.currency}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
            if (!it.isAvailable) Padding(padding: const EdgeInsets.only(top: 4), child: Text(s.t('cat.unavailable'), style: const TextStyle(color: AppColors.danger))),
            const SizedBox(height: 16),
            _Row(s.t('cat.dimensions'), it.dimensions),
            if (it.material.isNotEmpty) _Row(s.t('cat.material'), it.material),
            if (it.color.isNotEmpty) _Row(s.t('cat.color'), it.color),
            if (it.leadTimeDays != null) _Row(s.t('cat.leadTime'), s.f('cat.days', {'n': '${it.leadTimeDays}'})),
            if (it.workshopName != null) _Row(s.t('cat.workshop'), it.workshopName!),
            _Row(s.t('cat.model'), it.modelSource == 'uploaded' ? s.t('cat.model.uploaded') : s.t('cat.model.parametric')),
            if (it.description.isNotEmpty) ...[const SizedBox(height: 12), Text(it.description)],
            const SizedBox(height: 24),
            AppButton(label: s.t('cat.addToRoom'), icon: LucideIcons.plus, onPressed: it.isAvailable ? () => _addToRoom(context, ref, it) : null),
          ]),
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row(this.k, this.v);
  final String k;
  final String v;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 120, child: Text(k, style: const TextStyle(color: AppColors.textMuted))),
          Expanded(child: Text(v)),
        ]),
      );
}
