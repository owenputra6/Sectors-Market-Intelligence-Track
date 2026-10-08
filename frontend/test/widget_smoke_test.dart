import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sectors_duel_app/models/duel_models.dart';
import 'package:sectors_duel_app/screens/compare_screen.dart';
import 'package:sectors_duel_app/screens/fingerprint_screen.dart';
import 'package:sectors_duel_app/services/duel_api.dart';

void main() {
  testWidgets('CSV browse handles narrow and wide screens without overflow', (tester) async {
    for (final size in [const Size(1280,900), const Size(390,844), const Size(320,640)]) {
      await tester.binding.setSurfaceSize(size);
      await tester.pumpWidget(const MaterialApp(home: FingerprintScreen(initialData: {
        'meta': {'ready':false}, 'items': [],
      })));
      await tester.pumpAndSettle();
      expect(find.text('Every stock has a fingerprint.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    }
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('navbar omits AI and search exposes ranked recommendations', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 900));
    await tester.pumpWidget(const MaterialApp(home: FingerprintScreen(initialData: {
      'meta': {'ready': true},
      'items': [
        {'ticker': 'BBCA', 'company_name': 'Bank Central Asia', 'score': 75.0, 'overall_rank': 1, 'coverage': 1.0},
        {'ticker': 'PANI', 'company_name': 'Pantai Indah Kapuk Dua', 'score': 55.0, 'overall_rank': 2, 'coverage': 1.0},
      ],
    })));
    await tester.tap(find.byType(TextField).first);
    await tester.enterText(find.byType(TextField).first, 'pan');
    await tester.pumpAndSettle();
    expect(find.text('PANI'), findsWidgets);
    await tester.enterText(find.byType(TextField).first, '2');
    await tester.pumpAndSettle();
    expect(find.text('PANI'), findsWidgets);
    expect(find.text('BBCA'), findsNothing);
    expect(find.text('AI'), findsNothing);
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('compare autocomplete accepts a numeric rank', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: CompareScreen(
          api: DuelApi('http://127.0.0.1:8000'),
          stocks: const <JsonMap>[
            {'ticker': 'BBCA', 'company_name': 'Bank Central Asia', 'score': 75.0, 'overall_rank': 1},
            {'ticker': 'PANI', 'company_name': 'Pantai Indah Kapuk Dua', 'score': 55.0, 'overall_rank': 2},
          ],
          onBack: () {},
        ),
      ),
    ));
    final firstField = find.byType(TextField).first;
    await tester.tap(firstField);
    await tester.enterText(firstField, '2');
    await tester.pumpAndSettle();
    expect(find.text('PANI'), findsWidgets);
  });

  testWidgets('compare recommendation is directly selectable', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: CompareScreen(
          api: DuelApi('http://127.0.0.1:8000'),
          stocks: const <JsonMap>[
            {'ticker': 'BBCA', 'company_name': 'Bank Central Asia', 'score': 75.0, 'overall_rank': 1},
            {'ticker': 'PANI', 'company_name': 'Pantai Indah Kapuk Dua', 'score': 55.0, 'overall_rank': 2},
          ],
          onBack: () {},
        ),
      ),
    ));
    final firstField = find.byType(TextField).first;
    await tester.tap(firstField);
    await tester.enterText(firstField, '2');
    await tester.pumpAndSettle();
    await tester.tap(find.text('PANI').last);
    await tester.pump();

    expect(tester.widget<TextField>(firstField).controller!.text, 'PANI');
  });

  testWidgets('compare starts empty and swap exchanges both tickers', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: CompareScreen(
          api: DuelApi('http://127.0.0.1:8000'),
          stocks: const <JsonMap>[],
          onBack: () {},
        ),
      ),
    ));
    final fields = find.byType(TextField);
    expect(tester.widget<TextField>(fields.at(0)).controller!.text, isEmpty);
    expect(tester.widget<TextField>(fields.at(1)).controller!.text, isEmpty);
    await tester.enterText(fields.at(0), 'BBCA');
    await tester.enterText(fields.at(1), 'PANI');
    await tester.tap(find.byTooltip('Swap stocks'));
    await tester.pump();
    expect(tester.widget<TextField>(fields.at(0)).controller!.text, 'PANI');
    expect(tester.widget<TextField>(fields.at(1)).controller!.text, 'BBCA');
  });
}
