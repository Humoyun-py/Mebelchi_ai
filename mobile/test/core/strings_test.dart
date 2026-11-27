import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/l10n/strings.dart';

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
}
