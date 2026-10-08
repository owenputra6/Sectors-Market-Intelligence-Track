import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/duel_models.dart';
import '../services/duel_api.dart';
import 'compare_screen.dart';

const _ink = Color(0xFF0C0F17);
const _muted = Color(0xFF626B7C);
const _rule = Color(0xFFE0E4EA);
const _soft = Color(0xFFF7F8FA);
const _lavender = Color(0xFF8B6BE8);
const _amber = Color(0xFFE59A13);
const _mint = Color(0xFF27AD7E);
const _blue = Color(0xFF5F78EE);
const _rose = Color(0xFFE46F91);

class MarketHomeScreen extends StatefulWidget {
  const MarketHomeScreen({
    super.key,
    this.initialData,
    this.initialSectors,
  });

  final JsonMap? initialData;
  final List<JsonMap>? initialSectors;

  @override
  State<MarketHomeScreen> createState() => _MarketHomeScreenState();
}

class _MarketHomeScreenState extends State<MarketHomeScreen> {
  final _api = DuelApi(
    const String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://127.0.0.1:8000',
    ),
  );
  final _search = TextEditingController();
  final _searchFocus = FocusNode();
  final _stockA = TextEditingController();
  final _stockB = TextEditingController();
  final _stockAFocus = FocusNode();
  final _stockBFocus = FocusNode();

  JsonMap _data = <String, dynamic>{};
  List<JsonMap> _sectors = <JsonMap>[];
  JsonMap? _profile;
  String? _selectedSector;
  String? _error;
  String _leaderSegment = 'Overall';
  String _sectorSegment = 'Overall';
  int _searchHighlight = 0;
  int _stockAHighlight = 0;
  int _stockBHighlight = 0;
  // A pointer tap moves focus before InkWell fires on Flutter web. Keeping the
  // list pinned prevents the target recommendation disappearing mid-tap.
  bool _searchSuggestionsPinned = false;
  bool _stockASuggestionsPinned = false;
  bool _stockBSuggestionsPinned = false;
  bool _compare = false;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _searchFocus.addListener(_redraw);
    _stockAFocus.addListener(_redraw);
    _stockBFocus.addListener(_redraw);
    if (widget.initialData != null) {
      _data = widget.initialData!;
      _sectors = widget.initialSectors ?? <JsonMap>[];
    } else {
      _load();
    }
  }

  @override
  void dispose() {
    _search.dispose();
    _searchFocus
      ..removeListener(_redraw)
      ..dispose();
    _stockA.dispose();
    _stockB.dispose();
    _stockAFocus
      ..removeListener(_redraw)
      ..dispose();
    _stockBFocus
      ..removeListener(_redraw)
      ..dispose();
    super.dispose();
  }

  void _redraw() {
    if (_searchFocus.hasFocus) _searchSuggestionsPinned = true;
    if (_stockAFocus.hasFocus) _stockASuggestionsPinned = true;
    if (_stockBFocus.hasFocus) _stockBSuggestionsPinned = true;
    if (mounted) setState(() {});
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await Future.wait([_api.browseStocks(), _api.sectors()]);
      if (!mounted) return;
      setState(() {
        _data = result[0];
        _sectors = asMapList(result[1]['items']);
      });
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<JsonMap> get _stocks => asMapList(_data['items']);

  String _retrievedLabel() {
    final meta = asMap(_data['meta']);
    final raw = '${meta['fetched_at'] ?? meta['oldest_source_at'] ?? ''}';
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return 'in September 2027';
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December',
    ];
    return 'in ${months[parsed.month - 1]} ${parsed.year}';
  }

  Future<void> _openStock(String ticker) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await _api.stockProfile(ticker);
      if (!mounted) return;
      setState(() {
        _profile = asMap(response['profile']);
        _compare = false;
        _selectedSector = null;
      });
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _home() {
    setState(() {
      _profile = null;
      _compare = false;
      _selectedSector = null;
      _sectorSegment = 'Overall';
      _error = null;
    });
  }

  void _openCompare() {
    setState(() {
      _compare = true;
      _profile = null;
      _selectedSector = null;
      _error = null;
    });
  }

  void _swap() {
    final previous = _stockA.text;
    _stockA.text = _stockB.text;
    _stockB.text = previous;
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: ThemeData(
        useMaterial3: true,
        brightness: Brightness.light,
        scaffoldBackgroundColor: Colors.white,
        colorScheme: ColorScheme.fromSeed(
          seedColor: _lavender,
          brightness: Brightness.light,
          surface: Colors.white,
        ),
        dividerColor: _rule,
        textTheme: const TextTheme(
          bodyMedium: TextStyle(color: _ink, fontSize: 14, height: 1.45),
        ),
      ),
      child: Scaffold(
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 18, 24, 54),
            child: Align(
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1240),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (_loading) const LinearProgressIndicator(minHeight: 2),
                    if (_error != null) _errorLine(),
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 220),
                      child: _compare
                          ? CompareScreen(
                              key: const ValueKey('compare-page'),
                              api: _api,
                              stocks: _stocks,
                              initialTicker: _stockA.text.trim().isEmpty
                                  ? null
                                  : _stockA.text.trim(),
                              initialTickerB: _stockB.text.trim().isEmpty
                                  ? null
                                  : _stockB.text.trim(),
                              onBack: _home,
                            )
                          : _profile != null
                          ? _stockPage(_profile!)
                          : _selectedSector != null
                          ? _sectorPage(_selectedSector!)
                          : _homePage(),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _errorLine() => Container(
    width: double.infinity,
    margin: const EdgeInsets.only(bottom: 18),
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
    color: const Color(0xFFFFF5DD),
    child: Row(
      children: [
        const Icon(Icons.warning_amber_rounded, size: 18, color: _amber),
        const SizedBox(width: 9),
        Expanded(child: Text(_error!, style: const TextStyle(color: _ink))),
        TextButton(onPressed: _load, child: const Text('Retry')),
      ],
    ),
  );

  Widget _homePage() => Column(
    key: const ValueKey('home-v4'),
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const SizedBox(height: 20),
      LayoutBuilder(
        builder: (_, constraints) => Text(
          'Watcher',
          style: TextStyle(
            color: _ink,
            fontSize: constraints.maxWidth < 650 ? 38 : 54,
            height: 1.04,
            letterSpacing: -2,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
      const SizedBox(height: 12),
      const Text(
        'Watcher stands watch over Indonesia\'s market, following every signal '
        'and carrying the clearest stock intelligence back to you.',
        style: TextStyle(color: _muted, fontSize: 17),
      ),
      const SizedBox(height: 10),
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 2),
            child: Icon(Icons.schedule_rounded, size: 16, color: _amber),
          ),
          const SizedBox(width: 7),
          Expanded(
            child: Text(
              'Due to limited coverage, data was last retrieved ${_retrievedLabel()}. '
              'Run refresh_selected_sectors.py to retrieve newer sector data.',
              style: const TextStyle(color: _muted, fontSize: 12),
            ),
          ),
        ],
      ),
      const SizedBox(height: 28),
      LayoutBuilder(
        builder: (_, constraints) {
          if (constraints.maxWidth < 900) {
            return Column(
              children: [
                KeyedSubtree(
                  key: const Key('home-search'),
                  child: _searchBox(),
                ),
                const SizedBox(height: 22),
                _compareLauncher(),
              ],
            );
          }
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                flex: 14,
                child: KeyedSubtree(
                  key: const Key('home-search'),
                  child: _searchBox(),
                ),
              ),
              const SizedBox(width: 26),
              Expanded(flex: 10, child: _compareLauncher()),
            ],
          );
        },
      ),
      const SizedBox(height: 42),
      _marketLeaders(),
      const SizedBox(height: 46),
      _sectorDirectory(),
    ],
  );

  Iterable<JsonMap> _searchOptions(TextEditingValue value) {
    final query = value.text.trim().toLowerCase();
    final rank = int.tryParse(query.replaceFirst('#', ''));
    final rows = _stocks.where((row) {
      if (query.isEmpty) return true;
      if (rank != null) return asInt(row['overall_rank']) == rank;
      return '${row['ticker']} ${row['company_name']}'
          .toLowerCase()
          .contains(query);
    }).toList()
      ..sort((a, b) => (asDouble(b['score']) ?? -1)
          .compareTo(asDouble(a['score']) ?? -1));
    return rows.take(8);
  }

  KeyEventResult _handleSearchKey(FocusNode _, KeyEvent event) {
    if (event is! KeyDownEvent || !_searchFocus.hasFocus) {
      return KeyEventResult.ignored;
    }
    final rows = _searchOptions(
      TextEditingValue(text: _search.text),
    ).toList(growable: false);
    if (rows.isEmpty) return KeyEventResult.ignored;
    if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
      setState(() => _searchHighlight = (_searchHighlight + 1) % rows.length);
      return KeyEventResult.handled;
    }
    if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
      setState(
        () => _searchHighlight =
            (_searchHighlight - 1 + rows.length) % rows.length,
      );
      return KeyEventResult.handled;
    }
    if (event.logicalKey == LogicalKeyboardKey.enter) {
      _chooseSearchResult(
        rows[_searchHighlight.clamp(0, rows.length - 1).toInt()],
      );
      return KeyEventResult.handled;
    }
    if (event.logicalKey == LogicalKeyboardKey.escape) {
      setState(() => _searchSuggestionsPinned = false);
      _searchFocus.unfocus();
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  void _chooseSearchResult(JsonMap row) {
    _search.text = '${row['ticker']}';
    _searchSuggestionsPinned = false;
    _searchFocus.unfocus();
    _openStock('${row['ticker']}');
  }

  Widget _searchBox() {
    final rows = _searchOptions(
      TextEditingValue(text: _search.text),
    ).toList(growable: false);
    final showSuggestions =
        _searchFocus.hasFocus || _searchSuggestionsPinned;
    if (_searchHighlight >= rows.length) _searchHighlight = 0;
    return Focus(
      onKeyEvent: _handleSearchKey,
      child: Column(
        children: [
          TextField(
            controller: _search,
            focusNode: _searchFocus,
            onTap: () => setState(() => _searchSuggestionsPinned = true),
            onChanged: (_) => setState(() {
              _searchHighlight = 0;
              _searchSuggestionsPinned = true;
            }),
            onSubmitted: (_) {
              if (rows.isNotEmpty) _chooseSearchResult(rows[_searchHighlight]);
            },
            textCapitalization: TextCapitalization.characters,
            decoration: InputDecoration(
              hintText: 'Search ticker, company, or rank',
              prefixIcon: const Icon(Icons.search_rounded),
              suffixIcon: _search.text.isEmpty
                  ? null
                  : IconButton(
                      tooltip: 'Clear',
                      onPressed: () {
                        _search.clear();
                        _searchFocus.requestFocus();
                        setState(() {
                          _searchHighlight = 0;
                          _searchSuggestionsPinned = true;
                        });
                      },
                      icon: const Icon(Icons.close_rounded),
                    ),
              filled: true,
              fillColor: Colors.white,
              contentPadding: const EdgeInsets.symmetric(vertical: 19),
              enabledBorder: const OutlineInputBorder(
                borderSide: BorderSide(color: _rule),
                borderRadius: BorderRadius.all(Radius.circular(8)),
              ),
              focusedBorder: const OutlineInputBorder(
                borderSide: BorderSide(color: _blue, width: 1.5),
                borderRadius: BorderRadius.all(Radius.circular(8)),
              ),
            ),
          ),
          if (showSuggestions)
            Container(
              key: const Key('search-suggestions'),
              width: double.infinity,
              constraints: const BoxConstraints(maxHeight: 356),
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(
                  left: BorderSide(color: _rule),
                  right: BorderSide(color: _rule),
                  bottom: BorderSide(color: _rule),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Color(0x140C0F17),
                    blurRadius: 18,
                    offset: Offset(0, 8),
                  ),
                ],
              ),
              child: rows.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.all(16),
                      child: Text(
                        'No matching ticker, company, or rank.',
                        style: TextStyle(color: _muted),
                      ),
                    )
                  : ListView.separated(
                      padding: EdgeInsets.zero,
                      shrinkWrap: true,
                      itemCount: rows.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (_, index) {
                        final row = rows[index];
                        return InkWell(
                          onTap: () => _chooseSearchResult(row),
                          child: Container(
                            color: index == _searchHighlight
                                ? const Color(0xFFF0F4FC)
                                : Colors.white,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 13,
                            ),
                            child: Row(
                              children: [
                                SizedBox(
                                  width: 46,
                                  child: Text(
                                    '#${asInt(row['overall_rank'])}',
                                    style: const TextStyle(color: _muted),
                                  ),
                                ),
                                SizedBox(
                                  width: 70,
                                  child: Text(
                                    '${row['ticker']}',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w800,
                                    ),
                                  ),
                                ),
                                Expanded(
                                  child: Text(
                                    '${row['company_name'] ?? ''}',
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(color: _muted),
                                  ),
                                ),
                                Text(
                                  _percent(row['score']),
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
        ],
      ),
    );
  }

  Widget _compareLauncher() => Container(
    key: const Key('compare-launcher'),
    width: double.infinity,
    padding: const EdgeInsets.all(24),
    decoration: BoxDecoration(
      border: Border.all(color: _rule),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Compare two stocks',
          style: TextStyle(fontSize: 23, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 18),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: _tickerInput(
                'First stock',
                _stockA,
                _stockAFocus,
                'e.g. BUKA',
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(top: 20),
              child: IconButton(
                tooltip: 'Swap stocks',
                onPressed: _swap,
                icon: const Icon(Icons.swap_horiz_rounded),
              ),
            ),
            Expanded(
              child: _tickerInput(
                'Second stock',
                _stockB,
                _stockBFocus,
                'e.g. BBCA',
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            key: const Key('home-compare-button'),
            onPressed: _openCompare,
            style: FilledButton.styleFrom(
              backgroundColor: _ink,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 15),
            ),
            child: const Text('Compare'),
          ),
        ),
      ],
    ),
  );

  List<JsonMap> _tickerOptionsFor(TextEditingController controller) =>
      _searchOptions(TextEditingValue(text: controller.text))
          .take(5)
          .toList(growable: false);

  int _tickerHighlight(TextEditingController controller) =>
      identical(controller, _stockA) ? _stockAHighlight : _stockBHighlight;

  bool _tickerSuggestionsPinned(TextEditingController controller) =>
      identical(controller, _stockA)
          ? _stockASuggestionsPinned
          : _stockBSuggestionsPinned;

  void _setTickerHighlight(TextEditingController controller, int value) {
    if (identical(controller, _stockA)) {
      _stockAHighlight = value;
    } else {
      _stockBHighlight = value;
    }
  }

  void _setTickerSuggestionsPinned(
    TextEditingController controller,
    bool value,
  ) {
    if (identical(controller, _stockA)) {
      _stockASuggestionsPinned = value;
    } else {
      _stockBSuggestionsPinned = value;
    }
  }

  void _chooseTicker(TextEditingController controller, JsonMap row) {
    controller.text = '${row['ticker']}';
    setState(() {
      _setTickerHighlight(controller, 0);
      _setTickerSuggestionsPinned(controller, false);
      if (identical(controller, _stockA)) {
        _stockBSuggestionsPinned = true;
      }
    });
    if (identical(controller, _stockA)) {
      _stockBFocus.requestFocus();
    } else {
      _stockBFocus.unfocus();
    }
  }

  KeyEventResult _handleTickerKey(
    KeyEvent event,
    TextEditingController controller,
    FocusNode focusNode,
  ) {
    if (event is! KeyDownEvent || !focusNode.hasFocus) {
      return KeyEventResult.ignored;
    }
    final rows = _tickerOptionsFor(controller);
    if (rows.isEmpty) return KeyEventResult.ignored;
    var highlighted = _tickerHighlight(controller);
    if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
      highlighted = (highlighted + 1) % rows.length;
    } else if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
      highlighted = (highlighted - 1 + rows.length) % rows.length;
    } else if (event.logicalKey == LogicalKeyboardKey.enter) {
      _chooseTicker(
        controller,
        rows[highlighted.clamp(0, rows.length - 1).toInt()],
      );
      return KeyEventResult.handled;
    } else if (event.logicalKey == LogicalKeyboardKey.escape) {
      setState(() => _setTickerSuggestionsPinned(controller, false));
      focusNode.unfocus();
      return KeyEventResult.handled;
    } else {
      return KeyEventResult.ignored;
    }
    setState(() => _setTickerHighlight(controller, highlighted));
    return KeyEventResult.handled;
  }

  Widget _tickerInput(
    String label,
    TextEditingController controller,
    FocusNode focusNode,
    String hint,
  ) {
    final rows = _tickerOptionsFor(controller);
    final highlighted = _tickerHighlight(controller)
        .clamp(0, rows.isEmpty ? 0 : rows.length - 1)
        .toInt();
    return Focus(
      onKeyEvent: (_, event) => _handleTickerKey(event, controller, focusNode),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: controller,
            focusNode: focusNode,
            onTap: () => setState(
              () => _setTickerSuggestionsPinned(controller, true),
            ),
            onChanged: (_) => setState(() {
              _setTickerHighlight(controller, 0);
              _setTickerSuggestionsPinned(controller, true);
            }),
            onSubmitted: (_) {
              if (rows.isNotEmpty) _chooseTicker(controller, rows[highlighted]);
            },
            textCapitalization: TextCapitalization.characters,
            decoration: InputDecoration(
              labelText: label,
              hintText: hint,
              border: const UnderlineInputBorder(),
            ),
          ),
          if (focusNode.hasFocus || _tickerSuggestionsPinned(controller))
            Container(
              width: double.infinity,
              constraints: const BoxConstraints(maxHeight: 205),
              decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(
                  left: BorderSide(color: _rule),
                  right: BorderSide(color: _rule),
                  bottom: BorderSide(color: _rule),
                ),
              ),
              child: rows.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.all(10),
                      child: Text('No matching stock', style: TextStyle(color: _muted, fontSize: 11)),
                    )
                  : ListView.builder(
                      shrinkWrap: true,
                      padding: EdgeInsets.zero,
                      itemCount: rows.length,
                      itemBuilder: (_, index) {
                        final row = rows[index];
                        return InkWell(
                          onTap: () => _chooseTicker(controller, row),
                          child: Container(
                            color: index == highlighted
                                ? const Color(0xFFF0F4FC)
                                : Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 9),
                            child: Row(
                              children: [
                                SizedBox(
                                  width: 42,
                                  child: Text(
                                    '${row['ticker']}',
                                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12),
                                  ),
                                ),
                                Expanded(
                                  child: Text(
                                    '#${asInt(row['overall_rank'])} · ${row['company_name'] ?? ''}',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(color: _muted, fontSize: 10),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
        ],
      ),
    );
  }

  Widget _marketLeaders() {
    const segments = [
      'Overall',
      'Valuation',
      'Growth',
      'Financial',
      'Performance',
      'Dividend',
    ];
    final rows = [..._stocks]..sort((a, b) {
      if (_leaderSegment == 'Overall') {
        return (asDouble(b['score']) ?? -1).compareTo(asDouble(a['score']) ?? -1);
      }
      final aAxis = asMap(asMap(a['axes'])[_leaderSegment]);
      final bAxis = asMap(asMap(b['axes'])[_leaderSegment]);
      return (asDouble(bAxis['score']) ?? -1)
          .compareTo(asDouble(aAxis['score']) ?? -1);
    });
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Market leaders', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800)),
        const SizedBox(height: 12),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final segment in segments)
                TextButton(
                  onPressed: () => setState(() => _leaderSegment = segment),
                  style: TextButton.styleFrom(
                    foregroundColor: _segmentColor(segment),
                    shape: const RoundedRectangleBorder(),
                    side: BorderSide(
                      color: _leaderSegment == segment
                          ? _segmentColor(segment)
                          : Colors.transparent,
                      width: 0,
                    ),
                  ),
                  child: Container(
                    padding: const EdgeInsets.only(bottom: 5),
                    decoration: BoxDecoration(
                      border: Border(
                        bottom: BorderSide(
                          color: _leaderSegment == segment
                              ? _segmentColor(segment)
                              : Colors.transparent,
                          width: 2,
                        ),
                      ),
                    ),
                    child: Text(segment, style: const TextStyle(fontWeight: FontWeight.w700)),
                  ),
                ),
            ],
          ),
        ),
        const Divider(height: 1),
        for (var index = 0; index < rows.take(5).length; index++)
          _leaderRow(index + 1, rows[index]),
      ],
    );
  }

  Widget _leaderRow(int rank, JsonMap row) {
    final segment = '${row['dominant_axis'] ?? 'Insufficient evidence'}'
        .split(' / ')
        .first;
    final axis = asMap(asMap(row['axes'])[_leaderSegment]);
    final score = _leaderSegment == 'Overall' ? row['score'] : axis['score'];
    return LayoutBuilder(
      builder: (_, constraints) => InkWell(
        onTap: () => _openStock('${row['ticker']}'),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 13),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: _rule)),
          ),
          child: constraints.maxWidth < 620
              ? Row(
                  children: [
                    SizedBox(width: 34, child: Text('$rank', style: const TextStyle(color: _muted))),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${row['ticker']}', style: const TextStyle(fontWeight: FontWeight.w800)),
                          Text(
                            '${row['company_name'] ?? ''} · $segment',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(color: _segmentColor(segment), fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                    Text(_percent(score), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
                    const Icon(Icons.chevron_right_rounded, color: _muted),
                  ],
                )
              : Row(
                  children: [
                    SizedBox(width: 48, child: Text('$rank', style: const TextStyle(color: _muted))),
                    SizedBox(
                      width: 72,
                      child: Text('${row['ticker']}', style: const TextStyle(fontWeight: FontWeight.w800)),
                    ),
                    Expanded(
                      child: Text(
                        '${row['company_name'] ?? ''}',
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: _muted),
                      ),
                    ),
                    Text(_percent(score), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                    const SizedBox(width: 28),
                    SizedBox(
                      width: 132,
                      child: Text(
                        segment,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: _segmentColor(segment), fontWeight: FontWeight.w700),
                      ),
                    ),
                    const Icon(Icons.chevron_right_rounded, color: _muted),
                  ],
                ),
        ),
      ),
    );
  }

  Widget _sectorDirectory() {
    final groups = <String, List<JsonMap>>{};
    for (final row in _sectors) {
      groups.putIfAbsent('${row['sector']}', () => <JsonMap>[]).add(row);
    }
    final entries = groups.entries.toList()
      ..sort((a, b) => a.key.compareTo(b.key));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Indonesia Economic Sectors', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800)),
        const SizedBox(height: 6),
        const Text(
          'Choose a sector to open its own ranked company page.',
          style: TextStyle(color: _muted),
        ),
        const SizedBox(height: 22),
        LayoutBuilder(
          builder: (_, constraints) {
            final columns = constraints.maxWidth >= 980
                ? 3
                : constraints.maxWidth >= 620
                ? 2
                : 1;
            final width = (constraints.maxWidth - (columns - 1) * 34) / columns;
            return Wrap(
              spacing: 34,
              runSpacing: 30,
              children: [
                for (final entry in entries)
                  SizedBox(width: width, child: _sectorLink(entry.key, entry.value)),
              ],
            );
          },
        ),
      ],
    );
  }

  Widget _sectorLink(String sector, List<JsonMap> subsectors) {
    final companies = subsectors.fold<int>(
      0,
      (total, row) => total + asInt(row['total_companies']),
    );
    return InkWell(
      onTap: () => setState(() {
        _selectedSector = sector;
        _sectorSegment = 'Overall';
      }),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    sector,
                    style: const TextStyle(
                      fontSize: 19,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const Icon(Icons.arrow_forward_rounded, size: 18),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '${subsectors.length} subsectors  ·  $companies companies',
              style: const TextStyle(color: _muted),
            ),
            const SizedBox(height: 14),
            Text(
              'View company ranking →',
              style: TextStyle(
                color: _segmentColor('Valuation'),
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 10),
            const Divider(height: 1),
          ],
        ),
      ),
    );
  }

  Widget _sectorPage(String sector) {
    const segments = [
      'Overall',
      'Valuation',
      'Growth',
      'Financial',
      'Performance',
      'Dividend',
    ];
    final subsectors = _sectors.where((row) => '${row['sector']}' == sector).toList();
    final ranked = _stocks.where((row) => '${row['sector']}' == sector).toList()
      ..sort((a, b) {
        final byScore = (_sectorScore(b) ?? -1).compareTo(_sectorScore(a) ?? -1);
        return byScore != 0
            ? byScore
            : '${a['ticker']}'.compareTo('${b['ticker']}');
      });
    final totalCompanies = subsectors.fold<int>(
      0,
      (total, row) => total + asInt(row['total_companies']),
    );
    return Column(
      key: ValueKey('sector-$sector'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _back('All sectors', _home),
        const SizedBox(height: 24),
        Text(sector, style: const TextStyle(fontSize: 44, height: 1.05, fontWeight: FontWeight.w800, letterSpacing: -1.5)),
        const SizedBox(height: 8),
        Text(
          '${ranked.length} companies in the current snapshot  ·  '
          '${subsectors.length} subsectors  ·  $totalCompanies listed on IDX',
          style: const TextStyle(color: _muted, fontSize: 16),
        ),
        const SizedBox(height: 30),
        Text('$sector company ranking', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
        const SizedBox(height: 4),
        Text(
          'Rank every cached company in this sector by $_sectorSegment.',
          style: const TextStyle(color: _muted),
        ),
        const SizedBox(height: 12),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final segment in segments)
                TextButton(
                  key: Key('sector-axis-$segment'),
                  onPressed: () => setState(() => _sectorSegment = segment),
                  style: TextButton.styleFrom(
                    foregroundColor: _segmentColor(segment),
                    shape: const RoundedRectangleBorder(),
                  ),
                  child: Container(
                    padding: const EdgeInsets.only(bottom: 5),
                    decoration: BoxDecoration(
                      border: Border(
                        bottom: BorderSide(
                          color: _sectorSegment == segment
                              ? _segmentColor(segment)
                              : Colors.transparent,
                          width: 2,
                        ),
                      ),
                    ),
                    child: Text(
                      segment,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
            ],
          ),
        ),
        const Divider(height: 1),
        if (ranked.isNotEmpty)
          Container(
            padding: const EdgeInsets.symmetric(vertical: 11),
            child: Row(
              children: [
                const SizedBox(
                  width: 52,
                  child: Text('Rank', style: TextStyle(color: _muted, fontSize: 12)),
                ),
                const Expanded(
                  child: Text('Company', style: TextStyle(color: _muted, fontSize: 12)),
                ),
                Text(
                  _sectorSegment,
                  style: const TextStyle(color: _muted, fontSize: 12),
                ),
                const SizedBox(width: 42),
              ],
            ),
          ),
        if (ranked.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Text('No ranked companies from this sector are available in the current snapshot.'),
          )
        else
          for (var index = 0; index < ranked.length; index++)
            _sectorRankRow(index + 1, ranked[index], _sectorSegment),
        const SizedBox(height: 38),
        const Text(
          'Subsector benchmarks',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 6),
        const Text(
          'Reference medians used to normalize cross-subsector comparisons.',
          style: TextStyle(color: _muted),
        ),
        const SizedBox(height: 12),
        for (final row in subsectors)
          LayoutBuilder(
            builder: (_, constraints) => Container(
              padding: const EdgeInsets.symmetric(vertical: 11),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: _rule)),
              ),
              child: constraints.maxWidth < 620
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${row['sub_sector']}',
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          '${row['total_companies']} companies · '
                          'Median P/E ${_number(row['filtered_median_pe'])}x',
                          style: const TextStyle(color: _muted),
                        ),
                      ],
                    )
                  : Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${row['sub_sector']}',
                            style: const TextStyle(fontWeight: FontWeight.w700),
                          ),
                        ),
                        Text(
                          '${row['total_companies']} companies',
                          style: const TextStyle(color: _muted),
                        ),
                        const SizedBox(width: 26),
                        Text(
                          'Median P/E ${_number(row['filtered_median_pe'])}x',
                          style: const TextStyle(color: _muted),
                        ),
                      ],
                    ),
            ),
          ),
      ],
    );
  }

  double? _sectorScore(JsonMap row) {
    if (_sectorSegment == 'Overall') return asDouble(row['score']);
    return asDouble(asMap(asMap(row['axes'])[_sectorSegment])['score']);
  }

  Widget _sectorRankRow(int rank, JsonMap row, String segment) {
    final score = _sectorScore(row);
    final strongest = '${row['dominant_axis'] ?? 'Insufficient evidence'}'
        .split(' / ')
        .first;
    return InkWell(
      onTap: () => _openStock('${row['ticker']}'),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: _rule)),
        ),
        child: LayoutBuilder(
          builder: (_, constraints) => Row(
            children: [
              SizedBox(
                width: 52,
                child: Text(
                  '#$rank',
                  style: TextStyle(
                    color: _segmentColor(segment),
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              SizedBox(
                width: constraints.maxWidth < 620 ? 68 : 78,
                child: Text(
                  '${row['ticker']}',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${row['company_name'] ?? ''}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: _muted),
                    ),
                    if (constraints.maxWidth >= 620)
                      Text(
                        '${row['sub_sector'] ?? ''} · strongest: $strongest',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: _segmentColor(strongest),
                          fontSize: 11,
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Text(
                _percent(score),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
              const SizedBox(width: 16),
              const Icon(Icons.chevron_right_rounded, color: _muted),
            ],
          ),
        ),
      ),
    );
  }

  Widget _stockPage(JsonMap profile) {
    final axes = asMap(profile['axes']);
    final stock = asMap(profile['stock']);
    final benchmark = asMap(profile['benchmark']);
    return Column(
      key: ValueKey('stock-${profile['ticker']}'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            _back('Back', _home),
            const Spacer(),
            FilledButton.icon(
              onPressed: () {
                _stockA.text = '${profile['ticker']}';
                _stockB.clear();
                _openCompare();
              },
              style: FilledButton.styleFrom(backgroundColor: _ink, foregroundColor: Colors.white),
              icon: const Icon(Icons.compare_arrows_rounded),
              label: const Text('Compare'),
            ),
          ],
        ),
        const SizedBox(height: 24),
        Text('${profile['ticker']}', style: const TextStyle(fontSize: 48, fontWeight: FontWeight.w800, letterSpacing: -1.5)),
        Text('${profile['company_name'] ?? ''}  ·  ${profile['sector'] ?? ''} / ${profile['sub_sector'] ?? ''}', style: const TextStyle(color: _muted, fontSize: 16)),
        const SizedBox(height: 26),
        Wrap(
          spacing: 44,
          runSpacing: 18,
          children: [
            _fact('Duel win rate', _percent(profile['score'])),
            _fact('Overall rank', '#${profile['overall_rank']} of ${profile['overall_rank_total']}'),
            _fact('Coverage', _percent((asDouble(profile['coverage']) ?? 0) * 100)),
          ],
        ),
        const SizedBox(height: 38),
        const Text('Where the wins came from', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
        const SizedBox(height: 16),
        for (final entry in axes.entries) _axisRow(entry.key, asMap(entry.value), asInt(profile['opponents'])),
        const SizedBox(height: 34),
        const Text('What this means', style: TextStyle(fontSize: 25, fontWeight: FontWeight.w800)),
        const SizedBox(height: 10),
        Text('${profile['meaning'] ?? ''}', style: const TextStyle(color: _muted, fontSize: 15)),
        const SizedBox(height: 28),
        const Text('P/E sector evidence', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
        const SizedBox(height: 10),
        Text('${benchmark['sector']} → ${benchmark['sub_sector']}', style: const TextStyle(fontWeight: FontWeight.w700)),
        Text('${_number(stock['pe_ttm'])}x ÷ ${_number(benchmark['pe_median'])}x', style: const TextStyle(color: _lavender, fontSize: 24, fontWeight: FontWeight.w800)),
        const SizedBox(height: 22),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('15-feature evidence', style: TextStyle(fontWeight: FontWeight.w800)),
          children: [
            for (final row in asMapList(profile['features']))
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${row['number']}. ${row['label']}'),
                subtitle: Text('${row['segment']} · raw ${row['raw'] ?? 'N/A'} · baseline ${row['baseline'] ?? 'N/A'}'),
                trailing: Text(_number(row['value']), style: TextStyle(color: _segmentColor('${row['segment']}'), fontWeight: FontWeight.w800)),
              ),
          ],
        ),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('Data limitations', style: TextStyle(fontWeight: FontWeight.w800)),
          children: [
            for (final note in profile['limitations'] as List? ?? const [])
              ListTile(contentPadding: EdgeInsets.zero, leading: const Icon(Icons.info_outline), title: Text('$note')),
          ],
        ),
      ],
    );
  }

  Widget _fact(String label, String value) => SizedBox(
    width: 210,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: _muted)),
        const SizedBox(height: 3),
        Text(value, style: const TextStyle(fontSize: 27, fontWeight: FontWeight.w800)),
      ],
    ),
  );

  Widget _axisRow(String name, JsonMap axis, int opponents) {
    final score = asDouble(axis['score']);
    final missing = asInt(axis['unavailable']);
    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      childrenPadding: const EdgeInsets.only(bottom: 12),
      leading: Container(width: 8, height: 36, color: _segmentColor(name)),
      title: Text(name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
      subtitle: Text('${_percent(score)}  ·  ${axis['wins']}W ${axis['losses']}L ${axis['draws']}D'),
      trailing: Text(
        missing > 0
            ? 'Top ${axis['rank'] ?? '—'} · $missing missing'
            : 'Top ${axis['rank'] ?? '—'}',
        style: TextStyle(
          color: missing > 0 ? _amber : _segmentColor(name),
          fontWeight: FontWeight.w800,
          fontSize: 12,
        ),
      ),
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: Text('${axis['explanation'] ?? ''}\nCompared with $opponents scheduled opponents.', style: const TextStyle(color: _muted)),
        ),
      ],
    );
  }

  Widget _back(String label, VoidCallback onPressed) => TextButton.icon(
    onPressed: onPressed,
    style: TextButton.styleFrom(foregroundColor: _muted, padding: EdgeInsets.zero),
    icon: const Icon(Icons.arrow_back_rounded, size: 18),
    label: Text(label),
  );

  Color _segmentColor(String segment) {
    if (segment.contains('Valuation')) return _lavender;
    if (segment.contains('Growth')) return _amber;
    if (segment.contains('Financial')) return _mint;
    if (segment.contains('Performance')) return _blue;
    if (segment.contains('Dividend')) return _rose;
    return _ink;
  }

  String _percent(dynamic value) {
    final number = asDouble(value);
    return number == null ? 'N/A' : '${number.toStringAsFixed(1)}%';
  }

  String _number(dynamic value) {
    final number = asDouble(value);
    return number == null ? 'N/A' : number.toStringAsFixed(2);
  }
}
