import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../data/order_repository.dart';
import '../domain/order.dart';

final orderRepositoryProvider = Provider<OrderRepository>((ref) => OrderRepository(ref.watch(apiClientProvider)));

class OrderList {
  const OrderList(this.items, {required this.nextPage, required this.total});
  final List<WorkshopOrder> items;
  final int? nextPage;
  final int total;
}

/// The workshop's orders for one status filter, loaded page by page.
class OrdersController extends AutoDisposeFamilyAsyncNotifier<OrderList, String> {
  @override
  Future<OrderList> build(String arg) async {
    final p = await ref.read(orderRepositoryProvider).list(status: arg);
    return OrderList(p.results, nextPage: p.hasMore ? 2 : null, total: p.count);
  }

  Future<void> loadMore() async {
    final cur = state.value;
    if (cur == null || cur.nextPage == null) return;
    final p = await ref.read(orderRepositoryProvider).list(status: arg, page: cur.nextPage!);
    final ids = cur.items.map((e) => e.id).toSet();
    state = AsyncData(OrderList([...cur.items, ...p.results.where((e) => !ids.contains(e.id))], nextPage: p.hasMore ? cur.nextPage! + 1 : null, total: p.count));
  }
}

final ordersProvider = AsyncNotifierProvider.autoDispose.family<OrdersController, OrderList, String>(OrdersController.new);
final orderProvider = FutureProvider.autoDispose.family<WorkshopOrder, int>((ref, id) => ref.watch(orderRepositoryProvider).get(id));
