import 'transport_types.dart';

class PlatformTransport {
  Future<TransportResponse> postJson(Uri uri, String payload) {
    throw UnsupportedError('HTTP transport is not available on this platform.');
  }

  Future<TransportResponse> get(Uri uri) {
    throw UnsupportedError('HTTP transport is not available on this platform.');
  }
}
