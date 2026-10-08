// ignore_for_file: deprecated_member_use

import 'dart:html';

import 'transport_types.dart';

class PlatformTransport {
  Future<TransportResponse> postJson(Uri uri, String payload) async {
    final response = await HttpRequest.request(
      uri.toString(),
      method: 'POST',
      requestHeaders: const {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      sendData: payload,
    );
    return TransportResponse(
      statusCode: response.status ?? 0,
      body: response.responseText ?? '',
    );
  }

  Future<TransportResponse> get(Uri uri) async {
    final response = await HttpRequest.request(
      uri.toString(),
      method: 'GET',
      requestHeaders: const {'Accept': 'application/json'},
    );
    return TransportResponse(
      statusCode: response.status ?? 0,
      body: response.responseText ?? '',
    );
  }
}
