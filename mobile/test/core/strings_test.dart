import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/l10n/strings.dart';
import 'package:mebelchi_ai/features/projects/domain/project.dart';
import 'package:mebelchi_ai/features/calculator/domain/calculation.dart';

void main() {
  test('uz, ru and en have exactly the same keys', () {
    final en = stringTables['en']!.keys.toSet();
    for (final l in ['uz', 'ru']) {
      final k = stringTables[l]!.keys.toSet();
      expect(en.difference(k), isEmpty, reason: 'missing in $l');
      expect(k.difference(en), isEmpty, reason: 'extra in $l');
    }
  });

  test('placeholders are kept in every language', () {
    final re = RegExp(r'\{(\w+)\}');
    for (final key in stringTables['en']!.keys) {
      final want = re.allMatches(stringTables['en']![key]!).map((m) => m.group(1)).toSet();
      for (final l in ['uz', 'ru']) {
        expect(re.allMatches(stringTables[l]![key]!).map((m) => m.group(1)).toSet(), want, reason: '$key in $l');
      }
    }
  });

  test('f() fills placeholders and unknown keys fall back to the key', () {
    expect(const S('en').f('home.welcome', {'name': 'Ali'}), 'Hello, Ali');
    expect(const S('uz').t('no.such.key'), 'no.such.key');
  });

  test('every project category and cabinet option has a label in every language (no raw keys on screen)', () {
    for (final l in ['uz', 'ru', 'en']) {
      for (final c in projectCategories) {
        expect(stringTables[l]!.containsKey('cat.cat.$c'), isTrue, reason: 'cat.cat.$c in $l');
      }
      for (final t in cabinetTypes) {
        expect(stringTables[l]!.containsKey('calc.type.$t'), isTrue, reason: 'calc.type.$t in $l');
      }
      for (final h in handleStyles) {
        expect(stringTables[l]!.containsKey('calc.handle.$h'), isTrue, reason: 'calc.handle.$h in $l');
      }
    }
  });
}
