import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/l10n/strings.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/providers.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/workshop_orders/data/order_repository.dart';
import 'package:mebelchi_ai/features/workshop_orders/domain/order.dart';
import 'package:mebelchi_ai/features/workshop_orders/presentation/orders_screens.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../support/fake_adapter.dart';

Map<String, dynamic> row({int id = 1, String status = 'pending', List<String> next = const ['confirmed', 'rejected', 'cancelled'], bool money = true}) => {
      'id': id,
      'order_number': 'ORD-$id',
      'title': 'Kitchen $id',
      'description': 'Oak',
      'customer_name': 'Ali',
      'customer_phone': '+998901112233',
      'customer_address': 'Tashkent',
      'status': status,
      'allowed_next_statuses': next,
      if (money) 'total_price': '1500000.00',
      if (money) 'paid_amount': '0.00',
      'deadline': '2026-12-20',
      'status_history': [
        {'from_status': 'new', 'to_status': 'pending', 'note': '', 'created_at': '2026-11-27T10:00:00Z'},
      ],
    };

ApiClient _client(FakeAdapter a) => ApiClient(storage: MemoryTokenStorage(), baseUrl: 'http://x/api/v1', adapter: a);

void main() {
  test('every server status has a label and an action text in every language', () {
    for (final l in supportedLanguages) {
      for (final st in orderStatuses) {
        expect(stringTables[l]!.containsKey('order.status.$st'), isTrue, reason: 'status $st in $l');
        expect(stringTables[l]!.containsKey('order.action.$st'), isTrue, reason: 'action $st in $l');
      }
    }
  });

  test('action buttons: forward steps first, reject next, cancel last', () {
    expect(sortedActions(['cancelled', 'confirmed', 'rejected']), ['confirmed', 'rejected', 'cancelled']);
    expect(sortedActions(['cancelled', 'in_production', 'ready', 'quality_check']), ['in_production', 'quality_check', 'ready', 'cancelled']);
    expect(sortedActions(['zzz', 'cancelled']), ['cancelled', 'zzz']);
  });

  test('WorkshopOrder parses the allowed moves and tolerates missing money fields (employees)', () {
    final o = WorkshopOrder.fromJson(row());
    expect(o.waitingForAnswer, isTrue);
    expect(o.allowedNext, ['confirmed', 'rejected', 'cancelled']);
    expect(o.history.single.to, 'pending');
    final e = WorkshopOrder.fromJson(row(money: false));
    expect(e.totalPrice, isNull);
    expect(WorkshopOrder.fromJson({'id': 5}).allowedNext, isEmpty);
  });

  test('repository: filter, paging and status change with a note', () async {
    final a = FakeAdapter((o) => (status: 200, body: o.method == 'GET' && o.path == 'orders/' ? {'count': 1, 'next': null, 'previous': null, 'results': [row()]} : row(status: 'rejected', next: const [])));
    final repo = OrderRepository(_client(a));
    await repo.list(status: 'pending', page: 2);
    expect(a.log.last.queryParameters, {'status': 'pending', 'page': 2});
    await repo.list();
    expect(a.log.last.queryParameters, {'page': 1});
    await repo.setStatus(1, 'rejected', note: '  too far  ');
    expect(a.log.last.method, 'PATCH');
    expect(a.log.last.path, 'orders/1/');
    expect(a.log.last.data, {'status': 'rejected', 'status_note': 'too far'});
    await repo.setStatus(1, 'confirmed');
    expect(a.log.last.data, {'status': 'confirmed'});
  });

  Future<(FakeAdapter, Widget)> app() async {
    SharedPreferences.setMockInitialValues({'mebelchi.language': 'en'});
    final prefs = await SharedPreferences.getInstance();
    var current = row();
    final a = FakeAdapter((o) {
      if (o.method == 'PATCH') {
        current = row(status: o.data['status'] as String, next: const ['in_production', 'cancelled']);
        return (status: 200, body: current);
      }
      return (status: 200, body: current);
    });
    return (
      a,
      ProviderScope(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs), apiClientProvider.overrideWith((ref) => _client(a))],
        child: const MaterialApp(home: OrderDetailScreen(id: 1)),
      ),
    );
  }

  testWidgets('detail shows the customer, the server-allowed buttons, and accepting updates the buttons', (t) async {
    final (a, w) = await app();
    await t.pumpWidget(w);
    await t.pumpAndSettle();
    expect(find.text('Ali'), findsOneWidget);
    expect(find.text('+998901112233'), findsOneWidget);
    await t.scrollUntilVisible(find.text('Accept'), 200, scrollable: find.byType(Scrollable).first);
    expect(find.text('Accept'), findsOneWidget);
    expect(find.text('Reject'), findsOneWidget);
    expect(find.text('Move to production'), findsNothing); // not allowed by the server yet
    await t.tap(find.text('Accept'));
    await t.pumpAndSettle();
    expect(a.log.where((o) => o.method == 'PATCH').single.data, {'status': 'confirmed'});
    await t.scrollUntilVisible(find.text('Move to production'), 200, scrollable: find.byType(Scrollable).first);
    expect(find.text('Move to production'), findsOneWidget);
    expect(find.text('Accept'), findsNothing);
  });

  testWidgets('rejecting needs a reason and sends it', (t) async {
    final (a, w) = await app();
    await t.pumpWidget(w);
    await t.pumpAndSettle();
    await t.scrollUntilVisible(find.text('Reject'), 200, scrollable: find.byType(Scrollable).first);
    await t.tap(find.text('Reject'));
    await t.pumpAndSettle();
    await t.tap(find.widgetWithText(TextButton, 'Reject'));
    await t.pumpAndSettle();
    expect(a.log.where((o) => o.method == 'PATCH'), isEmpty); // empty reason is refused locally
    await t.enterText(find.byType(TextField), 'Too far away');
    await t.tap(find.widgetWithText(TextButton, 'Reject'));
    await t.pumpAndSettle();
    expect(a.log.where((o) => o.method == 'PATCH').single.data, {'status': 'rejected', 'status_note': 'Too far away'});
  });
}
