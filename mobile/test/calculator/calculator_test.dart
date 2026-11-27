import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/providers.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/calculator/data/calculator_repository.dart';
import 'package:mebelchi_ai/features/calculator/domain/calculation.dart';
import 'package:mebelchi_ai/features/calculator/presentation/calculator_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../support/fake_adapter.dart';

const _calc = {
  'input': {'width': 800},
  'summary': {
    'panel_count': 14,
    'total_area_m2': 4.0195,
    'edge_banding_m': 10.89,
    'by_material': {
      'MDF 18 mm': {'material': 'MDF', 'thickness': 18, 'area_m2': 2.6183, 'parts': 8, 'estimated_area_with_waste_m2': 3.011},
    },
  },
  'parts': [
    {'name': 'Side panel', 'width': 560, 'height': 720, 'thickness': 18, 'quantity': 2, 'material': 'MDF'},
  ],
  'hardware': [
    {'name': 'Hinge', 'quantity': 4, 'note': '2 per door'},
  ],
  'warnings': ['Door is narrow'],
  'assumptions': ['Overlay back panel'],
  'disclaimer': 'Calculated output for professional review. Not verified for manufacture.',
};

ApiClient _client(FakeAdapter a) => ApiClient(storage: MemoryTokenStorage(), baseUrl: 'http://x/api/v1', adapter: a);

void main() {
  test('CalcResult shows exactly what the server returned', () {
    final r = CalcResult.fromJson(_calc);
    expect(r.panelCount, 14);
    expect(r.totalAreaM2, 4.0195);
    expect(r.materials.single.label, 'MDF 18 mm');
    expect(r.materials.single.withWasteM2, 3.011);
    expect(r.parts.single.quantity, 2);
    expect(r.hardware.single.name, 'Hinge');
    expect(r.warnings, ['Door is narrow']);
    expect(r.savedId, isNull);
    expect(r.withSavedId(7).savedId, 7);
    expect(CalcResult.fromJson({}).panelCount, 0);
  });

  test('repository sends engine fields and only saves when asked', () async {
    final a = FakeAdapter((o) => (status: 200, body: o.path == 'cutting-lists/from-calculation/' ? {'id': 9} : o.path.endsWith('optimize/') ? {'sheet_count': 3, 'utilization_pct': 71.5} : {..._calc, if (o.data['save'] == true) 'saved_id': 5}));
    final repo = CalculatorRepository(_client(a));
    const input = CabinetInput(width: 800, height: 720, depth: 560, doors: 2);
    await repo.calculate(input);
    expect(a.log.last.path, 'calculations/material/');
    expect(a.log.last.data.containsKey('save'), isFalse);
    expect(a.log.last.data['cabinet_type'], 'standard');
    final saved = await repo.calculate(input, save: true, name: ' Wardrobe ', projectId: 4);
    expect(a.log.last.data['save'], isTrue);
    expect(a.log.last.data['name'], 'Wardrobe');
    expect(a.log.last.data['project'], 4);
    expect(saved.savedId, 5);
    final c = await repo.cuttingList(input, projectId: 4);
    expect(a.log.map((o) => o.path), containsAllInOrder(['cutting-lists/from-calculation/', 'cutting-lists/9/optimize/']));
    expect(c.sheetCount, 3);
    expect(c.utilizationPct, 71.5);
  });

  testWidgets('the screen calculates, shows the result with its disclaimer, and can save', (t) async {
    SharedPreferences.setMockInitialValues({'mebelchi.language': 'en'});
    final prefs = await SharedPreferences.getInstance();
    final a = FakeAdapter((o) => (status: 200, body: {..._calc, if (o.data['save'] == true) 'saved_id': 5}));
    await t.pumpWidget(ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs), apiClientProvider.overrideWith((ref) => _client(a))],
      child: const MaterialApp(home: CalculatorScreen()),
    ));
    await t.tap(find.text('Calculate'));
    await t.pumpAndSettle();
    expect(find.text('Side panel × 2'), findsOneWidget);
    expect(find.text('Door is narrow'), findsNothing); // shown with a bullet prefix
    expect(find.text('• Door is narrow'), findsOneWidget);
    await t.scrollUntilVisible(find.textContaining('Not verified for manufacture'), 200, scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('Not verified for manufacture'), findsOneWidget);
    await t.scrollUntilVisible(find.text('Save calculation'), 200, scrollable: find.byType(Scrollable).first);
    await t.tap(find.text('Save calculation'));
    await t.pumpAndSettle();
    expect(a.log.last.data['save'], isTrue);
    expect(find.text('Saved'), findsOneWidget);
  });

  testWidgets('a server validation error is shown instead of a result', (t) async {
    SharedPreferences.setMockInitialValues({'mebelchi.language': 'en'});
    final prefs = await SharedPreferences.getInstance();
    final a = FakeAdapter((o) => (status: 400, body: {'error': {'status': 400, 'detail': 'Invalid', 'fields': {'width': ['Must be between 200 and 4000 mm.']}}}));
    await t.pumpWidget(ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs), apiClientProvider.overrideWith((ref) => _client(a))],
      child: const MaterialApp(home: CalculatorScreen()),
    ));
    await t.tap(find.text('Calculate'));
    await t.pumpAndSettle();
    expect(find.textContaining('Must be between 200 and 4000 mm.'), findsOneWidget);
    expect(find.text('Parts list'), findsNothing);
  });
}
