import 'dart:convert';
import 'dart:io';

import 'transport_types.dart';

class PlatformTransport {
  Future<TransportResponse> postJson(Uri uri, String payload) async {
    final client = HttpClient();
    try {
      final request = await client.postUrl(uri);
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.add(utf8.encode(payload));
      final response = await request.close();
      final body = await utf8.decodeStream(response);
      return TransportResponse(statusCode: response.statusCode, body: body);
    } finally {
      client.close(force: true);
    }
  }

  Future<TransportResponse> get(Uri uri) async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(uri);
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      final response = await request.close();
      final body = await utf8.decodeStream(response);
      return TransportResponse(statusCode: response.statusCode, body: body);
    } finally {
      client.close(force: true);
    }
  }
}
