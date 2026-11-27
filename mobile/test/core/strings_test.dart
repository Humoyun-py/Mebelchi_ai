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

  test('names produced by the calculation engine are translated (uz/ru) and unknown ones pass through', () {
    const engineNames = [
      'Adjustable leg', 'Back panel', 'Back panel fixing', 'Bottom panel', 'Confirmat screw', 'Door', 'Drawer back', 'Drawer bottom', 'Drawer front',
      'Drawer inner front', 'Drawer side', 'Drawer slide (pair)', 'Front top rail', 'Handle', 'Hanging rail', 'Hinge', 'Plinth', 'Rear top rail', 'Shelf',
      'Shelf pin', 'Side panel', 'Sliding door', 'Sliding roller set', 'Sliding track (bottom)', 'Sliding track (top)', 'Top panel', 'Wall hanging bracket',
    ];
    for (final n in engineNames) {
      expect(const S('uz').engineName(n), isNot(n), reason: '$n has no uz text');
      expect(const S('ru').engineName(n), isNot(n), reason: '$n has no ru text');
    }
    expect(const S('uz').engineName('Something new'), 'Something new');
    expect(const S('en').engineName('Side panel'), 'Side panel');
  });

  test('common server validation messages are translated and a bare "Validation failed." is never shown when a field explains it', () {
    expect(const S('uz').serverText('overlaps another item (Dresser)'), contains('Dresser'));
    expect(const S('uz').serverText('overlaps another item (Dresser)'), isNot(contains('overlaps')));
    expect(const S('ru').serverText('taller than the room (2700 mm)'), contains('2700'));
    expect(const S('en').serverText('some other text'), 'some other text');
    expect(const S('uz').serverText('SMS is not configured on this server, so phone numbers cannot be verified.'), isNot(contains('configured')));
  });

  test('catalogue pieces have built-in names in every language (used when the question has no catalogue)', () {
    for (final slug in ['base-cabinet', 'wall-cabinet', 'drawer-base', 'wardrobe-2door', 'wardrobe-3door', 'tv-unit', 'bedside', 'dresser', 'bookcase', 'office-cabinet']) {
      for (final l in ['uz', 'ru', 'en']) {
        expect(S(l).templateName(slug, 'x'), isNot('x'), reason: '$slug in $l');
      }
    }
    expect(const S('uz').templateName('dresser', 'Dresser'), 'Komod');
    expect(const S('uz').templateName('custom-thing', 'My thing'), 'My thing');
    expect(const S('uz').templateName(null, 'Fallback'), 'Fallback');
  });
}
