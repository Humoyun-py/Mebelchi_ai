// Live-backend test of the workshop order flow. Needs MEBELCHI_E2E_URL and a seeded workshop owner with one pending order
// (MEBELCHI_E2E_SHOP_EMAIL / MEBELCHI_E2E_SHOP_PASSWORD). Skipped otherwise.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/authentication/data/auth_repository.dart';
import 'package:mebelchi_ai/features/workshop_orders/data/order_repository.dart';

void main() {
  final env = Platform.environment;
  final url = env['MEBELCHI_E2E_URL'];
  final email = env['MEBELCHI_E2E_SHOP_EMAIL'];
  final pass = env['MEBELCHI_E2E_SHOP_PASSWORD'];
  final skip = (url == null || email == null || pass == null) ? 'needs MEBELCHI_E2E_URL and the seeded workshop account' : false;

  test('a workshop answers a pending order: reject needs a reason, accept moves it through production', () async {
    final storage = MemoryTokenStorage();
    final api = ApiClient(storage: storage, baseUrl: url!);
    final session = await AuthRepository(api).login(email!, pass!);
    await storage.write(session.tokens);

    final repo = OrderRepository(api);
    final pending = await repo.list(status: 'pending');
    expect(pending.results, isNotEmpty);
    var o = await repo.get(pending.results.first.id);
    expect(o.status, 'pending');
    expect(o.allowedNext, containsAll(['confirmed', 'rejected']));
    expect(o.customerPhone, isNotEmpty);

    // the server insists on a reason for a rejection
    await expectLater(repo.setStatus(o.id, 'rejected'), throwsA(predicate((e) => e.toString().contains('validation'))));
    expect((await repo.get(o.id)).status, 'pending');

    o = await repo.setStatus(o.id, 'confirmed');
    expect(o.status, 'confirmed');
    expect(o.allowedNext, contains('in_production'));
    o = await repo.setStatus(o.id, 'in_production');
    expect(o.status, 'in_production');
    expect(o.allowedNext, containsAll(['quality_check', 'ready']));

    // an illegal jump is refused by the server, status unchanged
    await expectLater(repo.setStatus(o.id, 'delivered'), throwsA(anything));
    final after = await repo.get(o.id);
    expect(after.status, 'in_production');
    expect(after.history.map((h) => h.to), containsAll(['confirmed', 'in_production']));
    expect((await repo.list(status: 'in_production')).results.map((e) => e.id), contains(o.id));
  }, skip: skip);
}
