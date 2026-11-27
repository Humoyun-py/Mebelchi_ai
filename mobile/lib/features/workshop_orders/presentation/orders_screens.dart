import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/l10n/strings.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/state_views.dart';
import '../domain/order.dart';
import 'orders_controller.dart';

Color statusColor(String status) => switch (status) {
      'pending' || 'new' => const Color(0xFFB45309),
      'rejected' || 'cancelled' => AppColors.danger,
      'delivered' => AppColors.success,
      _ => AppColors.primary,
    };

String shortDate(String iso) => iso.length >= 10 ? iso.substring(0, 10) : iso;

class StatusChip extends ConsumerWidget {
  const StatusChip(this.status, {super.key});
  final String status;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(stringsProvider);
    final c = statusColor(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: c.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(20), border: Border.all(color: c.withValues(alpha: 0.4))),
      child: Text(s.t('order.status.$status'), style: TextStyle(color: c, fontWeight: FontWeight.w700, fontSize: 12)),
    );
  }
}

/// Orders the signed-in workshop owner (or assigned employee) can see. Marketplace orders arrive as "pending" and wait for an answer.
class OrdersScreen extends ConsumerStatefulWidget {
  const OrdersScreen({super.key});
  @override
  ConsumerState<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends ConsumerState<OrdersScreen> {
  String _filter = '';
  bool _loadingMore = false;

  Future<void> _more() async {
    if (_loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      await ref.read(ordersProvider(_filter).notifier).loadMore();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ref.read(stringsProvider).error(e))));
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final list = ref.watch(ordersProvider(_filter));
    return Scaffold(
      appBar: AppBar(title: Text(s.t('order.title'), style: const TextStyle(fontWeight: FontWeight.w700))),
      body: Column(children: [
        SizedBox(
          height: 52,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            itemCount: orderFilters.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (_, i) {
              final f = orderFilters[i];
              return ChoiceChip(label: Text(f.isEmpty ? s.t('order.filter.all') : s.t('order.status.$f')), selected: _filter == f, onSelected: (_) => setState(() => _filter = f));
            },
          ),
        ),
        Expanded(
          child: list.when(
            loading: () => const LoadingView(),
            error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(ordersProvider)),
            data: (data) {
              if (data.items.isEmpty) return EmptyView(icon: LucideIcons.packageOpen, title: s.t('order.empty.title'), message: s.t('order.empty.body'));
              return RefreshIndicator(
                onRefresh: () async => ref.invalidate(ordersProvider),
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                  itemCount: data.items.length + (data.nextPage != null ? 1 : 0),
                  separatorBuilder: (_, _) => const SizedBox(height: 8),
                  itemBuilder: (c, i) {
                    if (i == data.items.length) return AppButton(label: s.t('pr.more'), outlined: true, loading: _loadingMore, onPressed: _more);
                    final o = data.items[i];
                    return Card(
                      child: ListTile(
                        title: Text(o.title.isEmpty ? o.number : o.title, style: const TextStyle(fontWeight: FontWeight.w600)),
                        subtitle: Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text([o.number, o.customerName, if (o.deadline.isNotEmpty) shortDate(o.deadline)].where((e) => e.isNotEmpty).join(' · ')),
                        ),
                        trailing: StatusChip(o.status),
                        onTap: () => context.push('/orders/${o.id}'),
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

class OrderDetailScreen extends ConsumerStatefulWidget {
  const OrderDetailScreen({super.key, required this.id});
  final int id;
  @override
  ConsumerState<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends ConsumerState<OrderDetailScreen> {
  bool _busy = false;
  AppException? _error;

  Future<String?> _askNote(S s, String status) {
    final c = TextEditingController();
    final required = statusesNeedingReason.contains(status);
    return showDialog<String>(
      context: context,
      builder: (ctx) {
        String? err;
        return StatefulBuilder(
          builder: (ctx, set) => AlertDialog(
            title: Text(s.t('order.action.$status')),
            content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(s.t(required ? 'order.reasonRequired' : 'order.reasonOptional'), style: const TextStyle(color: AppColors.textMuted)),
              const SizedBox(height: 12),
              TextField(controller: c, maxLines: 3, maxLength: 255, decoration: InputDecoration(labelText: s.t('order.reason'), errorText: err)),
            ]),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: Text(s.t('common.cancel'))),
              TextButton(
                onPressed: () {
                  if (required && c.text.trim().isEmpty) {
                    set(() => err = s.t('auth.required'));
                    return;
                  }
                  Navigator.pop(ctx, c.text.trim());
                },
                child: Text(s.t('order.action.$status'), style: TextStyle(color: statusColor(status))),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _move(String status) async {
    final s = ref.read(stringsProvider);
    String note = '';
    if (statusesAskingConfirmation.contains(status)) {
      final got = await _askNote(s, status);
      if (got == null) return;
      note = got;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref.read(orderRepositoryProvider).setStatus(widget.id, status, note: note);
      ref.invalidate(orderProvider(widget.id));
      ref.invalidate(ordersProvider);
    } catch (e) {
      if (mounted) setState(() => _error = AppException.from(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final async = ref.watch(orderProvider(widget.id));
    return Scaffold(
      appBar: AppBar(),
      body: async.when(
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(error: e, onRetry: () => ref.invalidate(orderProvider(widget.id))),
        data: (o) {
          final err = _error;
          final msg = err == null ? null : (err.fields.isNotEmpty ? err.fields.values.expand((x) => x).join('\n') : s.error(err));
          return SafeArea(
            child: ListView(padding: const EdgeInsets.all(16), children: [
              Row(children: [Expanded(child: Text(o.title.isEmpty ? o.number : o.title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700))), StatusChip(o.status)]),
              const SizedBox(height: 4),
              Text(o.number, style: const TextStyle(color: AppColors.textMuted)),
              if (o.waitingForAnswer) ...[
                const SizedBox(height: 12),
                Card(color: AppColors.surfaceAlt, child: Padding(padding: const EdgeInsets.all(12), child: Text(s.t('order.waiting'), style: const TextStyle(fontWeight: FontWeight.w600)))),
              ],
              if (o.rejectionReason.isNotEmpty) ...[const SizedBox(height: 12), Text('${s.t('order.rejectedBecause')}: ${o.rejectionReason}', style: const TextStyle(color: AppColors.danger))],
              const SizedBox(height: 16),
              _Block(title: s.t('order.customer'), rows: [
                if (o.customerName.isNotEmpty) (LucideIcons.user, o.customerName),
                if (o.customerPhone.isNotEmpty) (LucideIcons.phone, o.customerPhone),
                if (o.customerAddress.isNotEmpty) (LucideIcons.mapPin, o.customerAddress),
              ]),
              if (o.description.isNotEmpty) ...[const SizedBox(height: 12), _Block(title: s.t('order.description'), rows: [(LucideIcons.fileText, o.description)])],
              if (o.totalPrice != null || o.deadline.isNotEmpty) ...[
                const SizedBox(height: 12),
                _Block(title: s.t('order.terms'), rows: [
                  if (o.totalPrice != null) (LucideIcons.banknote, '${s.t('order.total')}: ${o.totalPrice}'),
                  if (o.paidAmount != null) (LucideIcons.wallet, '${s.t('order.paid')}: ${o.paidAmount}'),
                  if (o.deadline.isNotEmpty) (LucideIcons.calendar, '${s.t('order.deadline')}: ${shortDate(o.deadline)}'),
                ]),
              ],
              if (msg != null) ...[const SizedBox(height: 12), FormError(msg)],
              if (o.allowedNext.isNotEmpty) ...[
                const SizedBox(height: 20),
                Text(s.t('order.actions'), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const SizedBox(height: 8),
                for (final n in sortedActions(o.allowedNext)) ...[
                  AppButton(label: s.t('order.action.$n'), outlined: !(n == 'confirmed' || n == 'in_production'), loading: _busy, onPressed: () => _move(n)),
                  const SizedBox(height: 8),
                ],
              ],
              if (o.history.isNotEmpty) ...[
                const SizedBox(height: 16),
                Text(s.t('order.history'), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                const SizedBox(height: 4),
                for (final h in o.history.reversed)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text(s.t('order.status.${h.to}')),
                    subtitle: Text([shortDate(h.at), if (h.note.isNotEmpty) h.note].join(' · ')),
                  ),
              ],
            ]),
          );
        },
      ),
    );
  }
}

class _Block extends StatelessWidget {
  const _Block({required this.title, required this.rows});
  final String title;
  final List<(IconData, String)> rows;
  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          for (final r in rows) Padding(padding: const EdgeInsets.only(bottom: 6), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(r.$1, size: 18, color: AppColors.textMuted), const SizedBox(width: 10), Expanded(child: SelectableText(r.$2))])),
        ]),
      ),
    );
  }
}
