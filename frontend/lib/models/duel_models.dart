typedef JsonMap = Map<String, dynamic>;

JsonMap asMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return value.map((key, item) => MapEntry('$key', item));
  return <String, dynamic>{};
}

List<JsonMap> asMapList(dynamic value) {
  if (value is! List) return const <JsonMap>[];
  return value.map(asMap).toList(growable: false);
}

double? asDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse('$value');
}

int asInt(dynamic value, [int fallback = 0]) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse('$value') ?? fallback;
}

class EstimateResult {
  EstimateResult(this.json);

  final JsonMap json;

  int get credits => asInt(json['estimated_new_credits_upper_bound']);
  bool get withinBudget => json['within_budget'] == true;
  List<JsonMap> get tickers => asMapList(json['tickers']);
}

class DuelReport {
  DuelReport(this.json);

  final JsonMap json;

  JsonMap get comparison => asMap(json['comparison']);
  JsonMap get verdict => asMap(json['verdict']);
  JsonMap get intelligence => asMap(json['market_intelligence']);
  JsonMap get meta => asMap(json['meta']);
  List<JsonMap> get features => asMapList(json['features']);
  List<JsonMap> get segments => asMapList(json['segments']);
  JsonMap get stocks => asMap(json['stocks']);

  String get tickerA => '${comparison['ticker_a'] ?? ''}';
  String get tickerB => '${comparison['ticker_b'] ?? ''}';
  String get winner => '${verdict['winner'] ?? 'unavailable'}';
  bool get available => verdict['available'] == true;
  String get narrative => '${json['narrative'] ?? ''}';

  JsonMap stock(String ticker) => asMap(stocks[ticker]);

  int featureWins(String ticker) {
    return features.where((row) => row['winner'] == ticker).length;
  }

  int get featureDraws => features.where((row) => row['winner'] == 'draw').length;

  double featurePointShare(String ticker) {
    final directKey = ticker == tickerA
        ? 'feature_point_share_a'
        : 'feature_point_share_b';
    final direct = asDouble(verdict[directKey]);
    if (direct != null) return direct;

    final valid = features
        .where((row) => row['reason'] != 'missing_data')
        .toList(growable: false);
    if (valid.isEmpty) return 0;
    final wins = valid.where((row) => row['winner'] == ticker).length;
    final draws = valid.where((row) => row['winner'] == 'draw').length;
    return 100 * (wins + draws * .5) / valid.length;
  }
}
