import 'package:flutter/material.dart';

import 'screens/market_home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SectorsDuelApp());
}

class SectorsDuelApp extends StatelessWidget {
  const SectorsDuelApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Watcher',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.light(useMaterial3: true),
      home: const MarketHomeScreen(),
    );
  }
}
