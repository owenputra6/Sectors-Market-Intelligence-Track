import 'package:flutter_test/flutter_test.dart';
import 'package:sectors_duel_app/models/duel_models.dart';

void main() {
  test('duel report exposes the backend contract', () {
    final report = DuelReport({
      'comparison': {'ticker_a': 'PANI', 'ticker_b': 'BBCA'},
      'verdict': {
        'available': true,
        'winner': 'BBCA',
        'feature_point_share_a': 25.0,
        'feature_point_share_b': 75.0,
      },
      'features': [
        {'winner': 'BBCA'},
        {'winner': 'draw'},
      ],
      'segments': List.generate(5, (index) => {'segment': '$index'}),
      'stocks': {
        'PANI': {'ticker': 'PANI'},
        'BBCA': {'ticker': 'BBCA'},
      },
      'market_intelligence': {'headline': 'BBCA leads'},
      'meta': {'sources': []},
    });

    expect(report.tickerA, 'PANI');
    expect(report.tickerB, 'BBCA');
    expect(report.winner, 'BBCA');
    expect(report.featureWins('BBCA'), 1);
    expect(report.featureDraws, 1);
    expect(report.featurePointShare('PANI'), 25.0);
    expect(report.featurePointShare('BBCA'), 75.0);
    expect(report.segments, hasLength(5));
    expect(report.intelligence['headline'], 'BBCA leads');
  });
}
