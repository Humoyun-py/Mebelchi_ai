import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mebelchi_ai/core/providers.dart';
import 'package:mebelchi_ai/features/room_designer/presentation/wizard_steps.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<void> _pump(WidgetTester t, Widget child) async {
  SharedPreferences.setMockInitialValues({'mebelchi.language': 'en'});
  final prefs = await SharedPreferences.getInstance();
  await t.pumpWidget(ProviderScope(overrides: [sharedPreferencesProvider.overrideWithValue(prefs)], child: MaterialApp(home: Scaffold(body: SingleChildScrollView(child: child)))));
}

const _label = {'en': 'X', 'uz': 'X', 'ru': 'X'};

void main() {
  testWidgets('ChoiceStep answers with the option id', (t) async {
    Object? got;
    await _pump(t, ChoiceStep(question: const {'options': [{'id': 'kitchen', 'label': {'en': 'Kitchen'}}, {'id': 'office', 'label': {'en': 'Office'}}]}, onSubmit: (v) async => got = v, busy: false));
    await t.tap(find.text('Office'));
    expect(got, 'office');
  });

  testWidgets('SizeStep validates the limits before sending', (t) async {
    Object? got;
    final q = {
      'value': null,
      'fields': [
        {'key': 'width', 'label': {'en': 'Width'}, 'min': 1000, 'max': 15000},
        {'key': 'length', 'label': {'en': 'Length'}, 'min': 1000, 'max': 15000},
        {'key': 'height', 'label': {'en': 'Height'}, 'min': 2000, 'max': 4500},
      ],
    };
    await _pump(t, SizeStep(question: q, onSubmit: (v) async => got = v, busy: false));
    final fields = find.byType(TextFormField);
    await t.enterText(fields.at(0), '500');
    await t.enterText(fields.at(1), '4000');
    await t.enterText(fields.at(2), '2700');
    await t.tap(find.text('Continue'));
    await t.pump();
    expect(got, isNull);
    expect(find.text('1000 to 15000'), findsWidgets);
    await t.enterText(fields.at(0), '3500');
    await t.tap(find.text('Continue'));
    await t.pump();
    expect(got, {'width': 3500, 'length': 4000, 'height': 2700});
  });

  testWidgets('SizeStep prefills the saved answer when the user comes back', (t) async {
    await _pump(t, SizeStep(question: const {'value': {'width': 3000, 'length': 4000, 'height': 2600}, 'fields': [{'key': 'width', 'label': _label, 'min': 1000, 'max': 15000}]}, onSubmit: (v) async {}, busy: false));
    expect(find.text('3000'), findsOneWidget);
  });

  testWidgets('ElementsStep sends counts and chosen furniture, respecting the maximum', (t) async {
    Object? got;
    final q = {
      'value': null,
      'fields': [
        {'key': 'doors', 'label': {'en': 'Doors'}, 'min': 0, 'max': 3, 'default': 1},
        {'key': 'windows', 'label': {'en': 'Windows'}, 'min': 0, 'max': 3, 'default': 1},
        {'key': 'furniture', 'label': {'en': 'Furniture'}, 'max': 1, 'options': [{'id': 'bed', 'label': {'en': 'Bed'}}, {'id': 'desk', 'label': {'en': 'Desk'}}]},
      ],
    };
    await _pump(t, ElementsStep(question: q, onSubmit: (v) async => got = v, busy: false));
    await t.tap(find.byTooltip('+').first); // doors 1 -> 2
    await t.tap(find.text('Bed'));
    await t.tap(find.text('Desk')); // over the maximum: ignored
    await t.pump();
    await t.tap(find.text('Continue'));
    await t.pump();
    expect(got, {'doors': 2, 'windows': 1, 'furniture': ['bed']});
  });

  testWidgets('OpeningsStep builds one valid opening per required door and window', (t) async {
    Object? got;
    final q = {
      'required': {'doors': 1, 'windows': 1},
      'walls': [{'id': 'north', 'label': {'en': 'North'}}, {'id': 'south', 'label': {'en': 'South'}}],
      'wall_lengths': {'north': 4000, 'south': 4000},
      'limits': {'door': {'width': [700, 1200], 'height': [1900, 2300]}, 'window': {'width': [400, 3000], 'height': [400, 2000], 'sill': [0, 1500]}},
      'value': null,
    };
    await _pump(t, OpeningsStep(question: q, onSubmit: (v) async => got = v, busy: false));
    await t.ensureVisible(find.text('Continue'));
    await t.pump();
    await t.tap(find.text('Continue'));
    await t.pump();
    final list = got as List;
    expect(list.length, 2);
    expect(list[0], {'type': 'door', 'wall': 'north', 'offset': 100, 'width': 900, 'height': 2100, 'sill': 0});
    expect((list[1] as Map)['type'], 'window');
    expect((list[1] as Map)['sill'], 900);
  });

  testWidgets('OpeningsStep narrows defaults to a short wall and explains an overflow instead of submitting', (t) async {
    Object? got;
    final q = {
      'required': {'doors': 0, 'windows': 1},
      'walls': [for (final w in ['north', 'east', 'south', 'west']) {'id': w, 'label': {'en': w}}],
      'wall_lengths': {'north': 1000, 'east': 1000, 'south': 1000, 'west': 1000},
      'limits': {'door': {'width': [700, 1200], 'height': [1900, 2300]}, 'window': {'width': [400, 3000], 'height': [400, 2000], 'sill': [0, 1500]}, 'edge_margin': 100},
      'value': null,
    };
    await _pump(t, OpeningsStep(question: q, onSubmit: (v) async => got = v, busy: false));
    await t.ensureVisible(find.text('Continue'));
    await t.tap(find.text('Continue'));
    await t.pump();
    final w = (got as List).single as Map; // the default 1200 mm window was narrowed to fit the 1000 mm wall with 100 mm margins
    expect(w['width'], 800);
    expect(w['offset'], 100);

    got = null;
    final fields = find.byType(TextFormField);
    await t.enterText(fields.at(1), '1200'); // width field of the single opening
    await t.ensureVisible(find.text('Continue'));
    await t.tap(find.text('Continue'));
    await t.pump();
    expect(got, isNull);
    expect(find.textContaining('1000 mm'), findsWidgets);
  });

  testWidgets('OpeningsStep places 2 doors and 4 windows in a 4 x 1 m room without misfits or overlaps', (t) async {
    Object? got;
    final q = {
      'required': {'doors': 2, 'windows': 4},
      'walls': [for (final w in ['north', 'east', 'south', 'west']) {'id': w, 'label': {'en': w}}],
      'wall_lengths': {'north': 4000, 'east': 1000, 'south': 4000, 'west': 1000},
      'limits': {'door': {'width': [600, 1200], 'height': [1800, 2400]}, 'window': {'width': [300, 3000], 'height': [300, 2400], 'sill': [0, 1500]}, 'edge_margin': 100, 'gap': 100},
      'value': null,
    };
    await _pump(t, OpeningsStep(question: q, onSubmit: (v) async => got = v, busy: false));
    for (var i = 0; i < 6 && find.text('Continue').evaluate().isEmpty; i++) {
      await t.pump();
    }
    await t.scrollUntilVisible(find.text('Continue'), 300, scrollable: find.byType(Scrollable).first);
    await t.tap(find.text('Continue'));
    await t.pump();
    final list = (got as List).cast<Map>();
    expect(list.length, 6, reason: 'a misfit would have blocked the submit');
    const len = {'north': 4000, 'east': 1000, 'south': 4000, 'west': 1000};
    for (final wall in len.keys) {
      final on = list.where((o) => o['wall'] == wall).toList()..sort((a, b) => (a['offset'] as int).compareTo(b['offset'] as int));
      for (var i = 0; i < on.length; i++) {
        expect(on[i]['offset'] as int, greaterThanOrEqualTo(100));
        expect((on[i]['offset'] as int) + (on[i]['width'] as int), lessThanOrEqualTo(len[wall]! - 100));
        if (i > 0) expect((on[i]['offset'] as int) - ((on[i - 1]['offset'] as int) + (on[i - 1]['width'] as int)), greaterThanOrEqualTo(100));
      }
    }
  });
}
