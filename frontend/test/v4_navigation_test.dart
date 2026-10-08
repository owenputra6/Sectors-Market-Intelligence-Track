import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sectors_duel_app/models/duel_models.dart';
import 'package:sectors_duel_app/screens/market_home_screen.dart';

const _stocks = <String, dynamic>{
  'meta': {'ready': true},
  'items': [
    {
      'ticker': 'BBCA',
      'company_name': 'Bank Central Asia',
      'sector': 'Financials',
      'sub_sector': 'Banks',
      'score': 94.8,
      'overall_rank': 1,
      'overall_rank_total': 2,
      'coverage': 1.0,
      'dominant_axis': 'Financial',
      'axes': {
        'Valuation': {'score': 40.0},
        'Financial': {'score': 93.3},
      },
    },
    {
      'ticker': 'BBRI',
      'company_name': 'Bank Rakyat Indonesia',
      'sector': 'Financials',
      'sub_sector': 'Banks',
      'score': 80.0,
      'overall_rank': 2,
      'overall_rank_total': 3,
      'coverage': 1.0,
      'dominant_axis': 'Valuation',
      'axes': {
        'Valuation': {'score': 90.0},
        'Financial': {'score': 72.0},
      },
    },
    {
      'ticker': 'PANI',
      'company_name': 'Pantai Indah Kapuk Dua',
      'sector': 'Properties & Real Estate',
      'sub_sector': 'Properties & Real Estate',
      'score': 61.2,
      'overall_rank': 3,
      'overall_rank_total': 3,
      'coverage': 1.0,
      'dominant_axis': 'Growth',
      'axes': {
        'Growth': {'score': 70.0},
      },
    },
  ],
};

const _sectors = <JsonMap>[
  {
    'sector': 'Financials',
    'sub_sector': 'Banks',
    'total_companies': 48,
    'filtered_median_pe': 8.93,
  },
  {
    'sector': 'Properties & Real Estate',
    'sub_sector': 'Properties & Real Estate',
    'total_companies': 93,
    'filtered_median_pe': 6.33,
  },
];

void main() {
  testWidgets('home has no global header and opens a dedicated sector ranking',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 1400));
    await tester.pumpWidget(const MaterialApp(
      home: MarketHomeScreen(initialData: _stocks, initialSectors: _sectors),
    ));
    await tester.pumpAndSettle();

    expect(find.text('IDX / FINGERPRINT'), findsNothing);
    expect(find.text('Indonesia Economic Sectors'), findsOneWidget);
    await tester.tap(find.text('Financials').last);
    await tester.pumpAndSettle();

    expect(find.text('Financials company ranking'), findsOneWidget);
    expect(find.text('#1'), findsOneWidget);
    expect(find.text('BBCA'), findsOneWidget);

    await tester.tap(find.byKey(const Key('sector-axis-Valuation')));
    await tester.pumpAndSettle();
    expect(
      tester.getTopLeft(find.text('BBRI')).dy,
      lessThan(tester.getTopLeft(find.text('BBCA')).dy),
    );
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('search recommendations render inline and support rank queries',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 1000));
    await tester.pumpWidget(const MaterialApp(
      home: MarketHomeScreen(initialData: _stocks, initialSectors: _sectors),
    ));
    await tester.pumpAndSettle();

    final search = find.descendant(
      of: find.byKey(const Key('home-search')),
      matching: find.byType(TextField),
    );
    await tester.tap(search);
    await tester.enterText(search, '2');
    await tester.pump();

    expect(find.byKey(const Key('search-suggestions')), findsOneWidget);
    final suggestions = find.byKey(const Key('search-suggestions'));
    expect(
      find.descendant(of: suggestions, matching: find.text('BBRI')),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: suggestions,
        matching: find.text('Bank Rakyat Indonesia'),
      ),
      findsOneWidget,
    );
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('search recommendation can be selected with a pointer tap',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 1000));
    await tester.pumpWidget(const MaterialApp(
      home: MarketHomeScreen(initialData: _stocks, initialSectors: _sectors),
    ));
    await tester.pumpAndSettle();

    final search = find.descendant(
      of: find.byKey(const Key('home-search')),
      matching: find.byType(TextField),
    );
    await tester.tap(search);
    await tester.pump();
    final recommendations = find.byKey(const Key('search-suggestions'));
    await tester.tap(
      find.descendant(of: recommendations, matching: find.text('BBRI')).first,
    );
    await tester.pump();

    expect(tester.widget<TextField>(search).controller!.text, 'BBRI');
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('home compare inputs recommend stocks while typing a rank',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 1000));
    await tester.pumpWidget(const MaterialApp(
      home: MarketHomeScreen(initialData: _stocks, initialSectors: _sectors),
    ));
    await tester.pumpAndSettle();

    final launcher = find.byKey(const Key('compare-launcher'));
    final firstStock = find.descendant(
      of: launcher,
      matching: find.byType(TextField),
    ).first;
    await tester.tap(firstStock);
    await tester.enterText(firstStock, '2');
    await tester.pump();

    expect(
      find.descendant(of: launcher, matching: find.text('BBRI')),
      findsOneWidget,
    );
    await tester.binding.setSurfaceSize(null);
  });

  testWidgets('compare launcher opens the full comparison page', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1280, 1000));
    await tester.pumpWidget(const MaterialApp(
      home: MarketHomeScreen(initialData: _stocks, initialSectors: _sectors),
    ));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).at(1), 'BBCA');
    await tester.enterText(find.byType(TextField).at(2), 'PANI');
    await tester.tap(find.byKey(const Key('home-compare-button')));
    await tester.pumpAndSettle();

    expect(find.text('Compare fingerprints.'), findsOneWidget);
    final fields = find.byType(TextField);
    expect(tester.widget<TextField>(fields.at(0)).controller!.text, 'BBCA');
    expect(tester.widget<TextField>(fields.at(1)).controller!.text, 'PANI');
    await tester.binding.setSurfaceSize(null);
  });
}
