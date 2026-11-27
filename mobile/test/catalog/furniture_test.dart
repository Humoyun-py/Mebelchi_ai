import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/furniture_catalog/data/catalog_repository.dart';
import 'package:mebelchi_ai/features/furniture_catalog/domain/furniture.dart';

import '../support/fake_adapter.dart';

const _row = {
  'id': 3, 'slug': 'bedside', 'category': 'bedroom', 'name': 'Bedside table', 'description': '', 'defaults': {'width': 450, 'height': 500, 'depth': 400},
  'price': '1200000.00', 'currency': 'UZS', 'material': 'MDF', 'color': 'white', 'workshop_name': null, 'lead_time_days': 7, 'is_available': true,
  'images': [{'view': 'front', 'url': '/api/v1/furniture/images/1/file/?sig=abc'}], 'model_source': 'parametric',
};

void main() {
  test('Furniture parses sizes and keeps the price exactly as sent', () {
    final f = Furniture.fromJson(Map<String, dynamic>.from(_row));
    expect(f.dimensions, '450 x 400 x 500 mm');
    expect(f.price, '1200000.00');
    expect(f.images.single.view, 'front');
    expect(f.workshopName, isNull);
  });

  test('a missing price stays null (never invented)', () {
    final f = Furniture.fromJson({..._row, 'price': null});
    expect(f.price, isNull);
  });

  test('the repository reads the plain array and sends filters', () async {
    final st = MemoryTokenStorage();
    final a = FakeAdapter((o) => (status: 200, body: [_row]));
    final repo = CatalogRepository(ApiClient(storage: st, baseUrl: 'http://x/api/v1', adapter: a));
    final rows = await repo.list(category: 'bedroom', search: ' bed ');
    expect(rows.single.slug, 'bedside');
    expect(a.log.single.queryParameters, {'category': 'bedroom', 'search': 'bed', 'is_available': true});
  });
}
