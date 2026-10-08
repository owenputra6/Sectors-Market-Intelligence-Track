import 'platform_transport_stub.dart'
    if (dart.library.io) 'platform_transport_io.dart'
    if (dart.library.html) 'platform_transport_web.dart';

export 'platform_transport_stub.dart'
    if (dart.library.io) 'platform_transport_io.dart'
    if (dart.library.html) 'platform_transport_web.dart';
export 'transport_types.dart';

PlatformTransport createPlatformTransport() => PlatformTransport();
