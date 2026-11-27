// Live-backend test of the calculator and cutting-list calls. Skipped unless MEBELCHI_E2E_URL is set.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/network/api_client.dart';
import 'package:mebelchi_ai/core/storage/token_storage.dart';
import 'package:mebelchi_ai/features/authentication/data/auth_repository.dart';
import 'package:mebelchi_ai/features/authentication/domain/user.dart';
import 'package:mebelchi_ai/features/calculator/data/calculator_repository.dart';
import 'package:mebelchi_ai/features/calculator/domain/calculation.dart';
import 'package:mebelchi_ai/features/projects/data/project_repository.dart';

void main() {
  final url = Platform.environment['MEBELCHI_E2E_URL'];
  final skip = url == null ? 'set MEBELCHI_E2E_URL to run against a live server' : false;

  test('calculate, save into a project, make a cutting list, and see server validation', () async {
    final storage = MemoryTokenStorage();
    final api = ApiClient(storage: storage, baseUrl: url!);
    final auth = AuthRepository(api);
    final session = await auth.register(firstName: 'Calc', lastName: 'Tester', email: 'calc${DateTime.now().microsecondsSinceEpoch}@example.com', password: 'Str0ng-pass-2026');
    await storage.write(session.tokens);
    await auth.setRole(UserRole.maker);

    final calc = CalculatorRepository(api);
    const input = CabinetInput(width: 800, height: 720, depth: 560, shelves: 1, doors: 2, drawers: 1);
    final r = await calc.calculate(input);
    expect(r.panelCount, greaterThan(0));
    expect(r.parts, isNotEmpty);
    expect(r.hardware.map((h) => h.name), contains('Hinge'));
    expect(r.disclaimer, contains('professional review'));
    expect(r.savedId, isNull);

    final project = await ProjectRepository(api).create(name: 'Calc project', category: 'cabinet');
    final saved = await calc.calculate(input, save: true, name: 'Wardrobe', projectId: project.id);
    expect(saved.savedId, isNotNull);
    final cut = await calc.cuttingList(input, name: 'Wardrobe cut', projectId: project.id);
    expect(cut.sheetCount, greaterThan(0));
    expect(cut.utilizationPct, inInclusiveRange(1, 100));
    final after = await ProjectRepository(api).get(project.id);
    expect(after.counts.calculations, 1);
    expect(after.counts.cuttingLists, 1);

    await expectLater(calc.calculate(const CabinetInput(width: 10, height: 720, depth: 560)), throwsA(predicate((e) => e.toString().contains('validation'))));
  }, skip: skip);
}
