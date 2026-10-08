import 'dart:convert';

import '../models/duel_models.dart';
import 'platform_transport.dart';

class ApiFailure implements Exception {
  const ApiFailure(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => statusCode == null ? message : '$statusCode · $message';
}

class DuelApi {
  DuelApi(String baseUrl)
    : baseUrl = baseUrl.trim().replaceFirst(RegExp(r'/$'), ''),
      _transport = createPlatformTransport();

  final String baseUrl;
  final PlatformTransport _transport;

  Future<JsonMap> browseStocks() async =>
      _decode(await _transport.get(Uri.parse('$baseUrl/api/v1/stocks')));
  Future<JsonMap> stockProfile(String ticker) async => _decode(
    await _transport.get(
      Uri.parse('$baseUrl/api/v1/stocks/${Uri.encodeComponent(ticker)}'),
    ),
  );
  Future<JsonMap> sectors() async =>
      _decode(await _transport.get(Uri.parse('$baseUrl/api/v1/sectors')));

  Future<JsonMap> health() async {
    return _decode(await _transport.get(Uri.parse('$baseUrl/health')));
  }

  Future<EstimateResult> estimate({
    required String tickerA,
    required String tickerB,
    required bool forceRefresh,
    required int maxNewCredits,
  }) async {
    final json = await _post(
      '/api/v1/duels/estimate',
      _payload(tickerA, tickerB, forceRefresh, maxNewCredits),
    );
    return EstimateResult(json);
  }

  Future<DuelReport> runDuel({
    required String tickerA,
    required String tickerB,
    required bool forceRefresh,
    required int maxNewCredits,
  }) async {
    final json = await _post(
      '/api/v1/duels',
      _payload(tickerA, tickerB, forceRefresh, maxNewCredits),
    );
    return DuelReport(json);
  }

  JsonMap _payload(String a, String b, bool force, int budget) => {
    'ticker_a': a.trim().toUpperCase().replaceAll('.JK', ''),
    'ticker_b': b.trim().toUpperCase().replaceAll('.JK', ''),
    'force_refresh': force,
    'max_new_credits': budget,
  };

  Future<JsonMap> _post(String path, JsonMap payload) async {
    final response = await _transport.postJson(
      Uri.parse('$baseUrl$path'),
      jsonEncode(payload),
    );
    return _decode(response);
  }

  JsonMap _decode(TransportResponse response) {
    dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      throw ApiFailure(
        response.body.isEmpty
            ? 'Backend returned an empty response.'
            : response.body,
        statusCode: response.statusCode,
      );
    }
    final map = asMap(decoded);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = map['detail'];
      final message = detail is String
          ? detail
          : '${asMap(detail)['message'] ?? detail ?? 'Request failed'}';
      throw ApiFailure(message, statusCode: response.statusCode);
    }
    return map;
  }
}
