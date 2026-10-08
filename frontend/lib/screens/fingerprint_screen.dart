import 'package:flutter/material.dart';

import '../services/duel_api.dart';
import '../models/duel_models.dart';
import 'compare_screen.dart';

const _bg = Color(0xFF121110);
const _surface = Color(0xFF1C1A1D);
const _border = Color(0xFF343137);
const _accent = Color(0xFFC3A2FF);
const _muted = Color(0xFFABA5B2);
const _green = Color(0xFF8EE2BD);

/// Read-only views of published weekly CSV snapshots. No Sectors key in Flutter.
class FingerprintScreen extends StatefulWidget {
  const FingerprintScreen({super.key, this.initialData, this.initialProfile});
  final JsonMap? initialData;
  final JsonMap? initialProfile;
  @override
  State<FingerprintScreen> createState() => _FingerprintScreenState();
}

class _FingerprintScreenState extends State<FingerprintScreen> {
  final _search = TextEditingController();
  final _api = DuelApi(
    const String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://127.0.0.1:8000',
    ),
  );
  JsonMap _data = {};
  JsonMap? _profile;
  List<JsonMap> _sectors = [];
  String? _error;
  bool _loading = false;
  bool _sectorView = false;
  bool _compareView = false;
  String? _compareInitialTicker;
  bool _descending = true;
  int _generation = 0;
  final _searchFocus = FocusNode();

  @override
  void initState() {
    super.initState();
    _searchFocus.addListener(_refreshSearchSuggestions);
    _profile = widget.initialProfile;
    if (widget.initialData != null) {
      _data = widget.initialData!;
    } else {
      _load();
    }
  }

  @override
  void dispose() {
    _search.dispose();
    _searchFocus.removeListener(_refreshSearchSuggestions);
    _searchFocus.dispose();
    super.dispose();
  }

  void _refreshSearchSuggestions() {
    if (mounted) setState(() {});
  }

  Future<void> _load() async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _api.browseStocks(),
        _api.sectors(),
      ]);
      if (!mounted || generation != _generation) return;
      setState(() {
        _data = results[0];
        _sectors = (results[1]['items'] as List? ?? []).map(asMap).toList();
        _profile = null;
        _sectorView = false;
        _compareView = false;
      });
    } catch (e) {
      if (mounted && generation == _generation)
        setState(() => _error = e.toString());
    } finally {
      if (mounted && generation == _generation)
        setState(() => _loading = false);
    }
  }

  Future<void> _open(String ticker) async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _api.stockProfile(ticker);
      if (!mounted || generation != _generation) return;
      setState(() {
        _profile = asMap(result['profile']);
        _data['meta'] = result['meta'];
        _sectorView = false;
        _compareView = false;
      });
    } catch (e) {
      if (mounted && generation == _generation)
        setState(() => _error = e.toString());
    } finally {
      if (mounted && generation == _generation)
        setState(() => _loading = false);
    }
  }

  Future<void> _openSectors() async {
    final generation = ++_generation;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await _api.sectors();
      if (!mounted || generation != _generation) return;
      setState(() {
        _sectors = (result['items'] as List? ?? []).map(asMap).toList();
        _sectorView = true;
        _profile = null;
        _compareView = false;
      });
    } catch (e) {
      if (mounted && generation == _generation)
        setState(() => _error = e.toString());
    } finally {
      if (mounted && generation == _generation)
        setState(() => _loading = false);
    }
  }

  void _goHome({bool focusSearch = false}) {
    setState(() {
      _profile = null;
      _sectorView = false;
      _compareView = false;
    });
    if (focusSearch) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _searchFocus.requestFocus());
    }
  }

  void _openCompare([String? ticker]) {
    setState(() {
      // Navbar Compare always starts empty. The detail-page button explicitly
      // passes its ticker when pre-filling Stock A is intentional.
      _compareInitialTicker = ticker;
      _sectorView = false;
      _compareView = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final meta = asMap(_data['meta']);
    return Theme(
      data: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: _bg,
        colorScheme: const ColorScheme.dark(
          primary: _accent,
          surface: _surface,
        ),
        dividerColor: _border,
        textTheme: const TextTheme(
          bodyMedium: TextStyle(fontSize: 14, height: 1.5),
        ),
      ),
      child: Scaffold(
        body: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 760;
              return SingleChildScrollView(
                padding: EdgeInsets.all(compact ? 12 : 32),
                child: Align(
                  alignment: Alignment.topCenter,
                  child: Container(
                    constraints: const BoxConstraints(maxWidth: 1320),
                    decoration: BoxDecoration(
                      color: const Color(0xFF111010),
                      border: Border.all(color: _border),
                      borderRadius: BorderRadius.circular(compact ? 18 : 24),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _topBar(compact),
                        const Divider(height: 1),
                        Padding(
                          padding: EdgeInsets.fromLTRB(
                            compact ? 18 : 34,
                            compact ? 24 : 32,
                            compact ? 18 : 34,
                            compact ? 28 : 38,
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _statusStrip(meta),
                              if (_loading)
                                const Padding(
                                  padding: EdgeInsets.only(top: 18),
                                  child: LinearProgressIndicator(minHeight: 2),
                                ),
                              if (_error != null) ...[
                                const SizedBox(height: 18),
                                _errorPanel(),
                              ],
                              const SizedBox(height: 28),
                              AnimatedSwitcher(
                                duration: const Duration(milliseconds: 260),
                                switchInCurve: Curves.easeOutCubic,
                                child: _compareView
                                    ? CompareScreen(
                                        key: const ValueKey('compare'),
                                        api: _api,
                                        stocks: (_data['items'] as List? ?? [])
                                            .map(asMap)
                                            .toList(),
                                        initialTicker: _compareInitialTicker,
                                        onBack: () => setState(() => _compareView = false),
                                      )
                                    : _sectorView
                                    ? _sectorDirectory()
                                    : _profile != null
                                    ? _detail(_profile!)
                                    : _home(),
                              ),
                              const SizedBox(height: 34),
                              _footer(meta),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _topBar(bool compact) {
    Widget action(String label, IconData icon, VoidCallback onPressed, {bool disabled = false}) {
      if (compact) {
        return IconButton(
          tooltip: label,
          onPressed: disabled ? null : onPressed,
          icon: Icon(icon, size: 20),
        );
      }
      return TextButton.icon(
        onPressed: disabled ? null : onPressed,
        icon: Icon(icon, size: 17),
        label: Text(label),
        style: TextButton.styleFrom(
          foregroundColor: _muted,
          padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 16),
        ),
      );
    }

    const brand = Text(
      'IDX / FINGERPRINT',
      style: TextStyle(
        fontSize: 16,
        fontWeight: FontWeight.w800,
        letterSpacing: 1.35,
      ),
    );
    if (compact) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(14, 8, 8, 8),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: _goHome,
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 4, vertical: 10),
                      child: FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: brand,
                      ),
                    ),
                  ),
                ),
                IconButton(
                  tooltip: 'Reload',
                  onPressed: _loading ? null : _load,
                  icon: const Icon(Icons.refresh_rounded, size: 20),
                ),
              ],
            ),
            Row(
              children: [
                Expanded(
                  child: TextButton.icon(
                    onPressed: () => _goHome(focusSearch: true),
                    icon: const Icon(Icons.search_rounded, size: 17),
                    label: const Text('Search'),
                  ),
                ),
                Expanded(
                  child: TextButton.icon(
                    onPressed: _openCompare,
                    icon: const Icon(Icons.compare_arrows_rounded, size: 17),
                    label: const Text('Compare'),
                  ),
                ),
                Expanded(child: TextButton.icon(onPressed: _openSectors, icon: const Icon(Icons.account_tree_outlined, size: 17), label: const Text('Sectors'))),
              ],
            ),
          ],
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 11),
      child: Row(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(8),
            onTap: _goHome,
            child: const Padding(
              padding: EdgeInsets.symmetric(horizontal: 4, vertical: 10),
              child: brand,
            ),
          ),
          const Spacer(),
          action('Search', Icons.search_rounded, () => _goHome(focusSearch: true)),
          action('Compare', Icons.compare_arrows_rounded, _openCompare),
          action('Sectors', Icons.account_tree_outlined, _openSectors),
          action('Reload', Icons.refresh_rounded, _load, disabled: _loading),
        ],
      ),
    );
  }

  Widget _statusStrip(JsonMap meta) {
    final partial = meta['partial'] == true;
    final available = meta['cohort_size_available'] ?? meta['cached_reports'];
    final expected = meta['cohort_size_expected'] ?? meta['cohort_size'];
    final coverage = available != null && expected != null
        ? '$available / $expected covered'
        : null;
    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 10,
      runSpacing: 9,
      children: [
        _tag('WEEKLY SNAPSHOT', _accent),
        _tag(
          partial
              ? 'CACHE-ONLY / PARTIAL'
              : (meta['ready'] == true
                    ? (meta['stale'] == true ? 'STALE DATA' : 'CSV CONNECTED')
                    : 'AWAITING DATA'),
          partial || meta['stale'] == true ? Colors.amber : _green,
        ),
        Text(
          [meta['cohort_name']?.toString() ?? 'Cohort pending', coverage]
              .whereType<String>()
              .join('  •  '),
          style: const TextStyle(color: _muted, fontSize: 13),
        ),
      ],
    );
  }

  Widget _home() {
    return Column(
      key: const ValueKey('home'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(
          builder: (context, c) => Text(
            'Every stock has a fingerprint.',
            style: TextStyle(
              fontSize: c.maxWidth < 620 ? 36 : 46,
              height: 1.08,
              fontWeight: FontWeight.w800,
              letterSpacing: -1.6,
            ),
          ),
        ),
        const SizedBox(height: 10),
        const Text(
          '15 fitur, 5 segmen, dan benchmark subsektor yang bisa ditelusuri.',
          style: TextStyle(color: _muted, fontSize: 16),
        ),
        const SizedBox(height: 26),
        _searchAutocomplete(),
        const SizedBox(height: 32),
        _browse(),
        const SizedBox(height: 38),
        _sectorPreview(),
      ],
    );
  }

  Iterable<JsonMap> _searchOptions(TextEditingValue value) {
    final query = value.text.trim().toLowerCase();
    final rankQuery = int.tryParse(query.replaceFirst('#', ''));
    final candidates = (_data['items'] as List? ?? []).map(asMap).where((row) {
      if (query.isEmpty) return true;
      if (rankQuery != null) return asInt(row['overall_rank']) == rankQuery;
      return '${row['ticker']} ${row['company_name']}'
          .toLowerCase()
          .contains(query);
    }).toList()
      ..sort((a, b) {
        final scoreA = asDouble(a['score']) ?? -1;
        final scoreB = asDouble(b['score']) ?? -1;
        final scoreOrder = scoreB.compareTo(scoreA);
        return scoreOrder != 0
            ? scoreOrder
            : '${a['ticker']}'.compareTo('${b['ticker']}');
      });
    return candidates.take(8);
  }

  Widget _searchAutocomplete() => RawAutocomplete<JsonMap>(
    textEditingController: _search,
    focusNode: _searchFocus,
    displayStringForOption: (row) => '${row['ticker']}',
    optionsBuilder: _searchOptions,
    onSelected: (row) {
      _searchFocus.unfocus();
      _open('${row['ticker']}');
    },
    fieldViewBuilder: (context, controller, focusNode, onSubmitted) => TextField(
      focusNode: focusNode,
      controller: controller,
      onChanged: (_) => setState(() {}),
      onSubmitted: (_) => onSubmitted(),
      textCapitalization: TextCapitalization.characters,
      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      decoration: InputDecoration(
        hintText: 'Cari ticker atau nama perusahaan',
        hintStyle: const TextStyle(color: _muted, fontWeight: FontWeight.w400),
        prefixIcon: const Icon(Icons.search_rounded),
        suffixIcon: _search.text.isEmpty
            ? null
            : IconButton(
                tooltip: 'Clear',
                onPressed: () {
                  _search.clear();
                  setState(() {});
                  _searchFocus.requestFocus();
                },
                icon: const Icon(Icons.close_rounded),
              ),
        filled: true,
        fillColor: _surface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 19),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: _border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: _accent, width: 1.4),
        ),
      ),
    ),
    optionsViewBuilder: (context, onSelected, options) {
      final rows = options.toList(growable: false);
      final width = MediaQuery.of(context).size.width > 760
          ? 680.0
          : MediaQuery.of(context).size.width - 48;
      return Align(
        alignment: Alignment.topLeft,
        child: Material(
          color: Colors.transparent,
          elevation: 12,
          child: Container(
            width: width,
            constraints: const BoxConstraints(maxHeight: 410),
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: const Color(0xFF171619),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _accent.withAlpha(100)),
            ),
            child: ListView.builder(
              padding: EdgeInsets.zero,
              shrinkWrap: true,
              itemCount: rows.length,
              itemBuilder: (itemContext, index) {
                final highlighted = AutocompleteHighlightedOption.of(itemContext) == index;
                return _recommendationRow(
                  rows[index],
                  highlighted: highlighted,
                  onTap: () => onSelected(rows[index]),
                );
              },
            ),
          ),
        ),
      );
    },
  );

  Widget _recommendationRow(
    JsonMap row, {
    required bool highlighted,
    required VoidCallback onTap,
  }) {
    final score = asDouble(row['score']);
    final rank = asInt(row['overall_rank']);
    return Material(
      color: highlighted ? _accent.withAlpha(24) : Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(9),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 10),
          child: Row(
            children: [
              if (rank > 0) ...[
                SizedBox(
                  width: 28,
                  child: Text('#$rank', style: TextStyle(color: rank <= 3 ? _accent : _muted, fontWeight: FontWeight.w800)),
                ),
                const SizedBox(width: 5),
              ],
              Container(width: 7, height: 7, decoration: const BoxDecoration(color: _green, shape: BoxShape.circle)),
              const SizedBox(width: 10),
              SizedBox(
                width: 68,
                child: Text('${row['ticker']}', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
              ),
              Expanded(
                child: Text(
                  '${row['company_name'] ?? ''}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: _muted, fontSize: 12),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                score == null ? 'N/A' : '${score.toStringAsFixed(1)}%',
                style: TextStyle(color: score == null ? _muted : _green, fontWeight: FontWeight.w800),
              ),
              const SizedBox(width: 3),
              const Icon(Icons.chevron_right_rounded, size: 18, color: _muted),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectorPreview() {
    final groups = <String, List<JsonMap>>{};
    for (final row in _sectors) {
      groups.putIfAbsent('${row['sector']}', () => []).add(row);
    }
    final entries = groups.entries.take(6).toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Expanded(
              child: Text(
                'INDONESIA ECONOMIC SECTORS',
                style: TextStyle(
                  color: _accent,
                  fontSize: 12,
                  letterSpacing: 1.05,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            TextButton.icon(
              onPressed: _openSectors,
              icon: const Icon(Icons.arrow_forward_rounded, size: 16),
              label: const Text('See all'),
            ),
          ],
        ),
        const SizedBox(height: 14),
        if (entries.isEmpty)
          _panel(const Text('Benchmark subsektor belum tersedia.'))
        else
          LayoutBuilder(
            builder: (context, c) {
              final columns = c.maxWidth >= 940 ? 3 : c.maxWidth >= 580 ? 2 : 1;
              final width = (c.maxWidth - (columns - 1) * 16) / columns;
              return Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  for (final entry in entries)
                    SizedBox(
                      width: width,
                      child: _sectorCard(entry.key, entry.value),
                    ),
                ],
              );
            },
          ),
      ],
    );
  }

  Widget _sectorCard(String sector, List<JsonMap> rows) {
    final median = rows.length == 1
        ? num.tryParse('${rows.first['filtered_median_pe']}')
        : null;
    final companies = rows.fold<int>(
      0,
      (sum, row) => sum + (int.tryParse('${row['total_companies']}') ?? 0),
    );
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(sector, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
          const SizedBox(height: 5),
          Text(
            rows.map((row) => '${row['sub_sector']}').take(2).join(' · '),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: _muted, fontSize: 12),
          ),
          const SizedBox(height: 18),
          Text(
            rows.length == 1
                ? 'median P/E  ${_num(median)}'
                : '${rows.length} subsector benchmarks',
            style: const TextStyle(color: _accent, fontWeight: FontWeight.w700),
          ),
          Text('$companies companies', style: const TextStyle(color: _muted, fontSize: 12)),
        ],
      ),
    );
  }

  Widget _errorPanel() => _panel(
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Belum bisa memuat data',
          style: TextStyle(color: Colors.amber, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 4),
        Text(_error ?? 'Unknown error'),
        TextButton(onPressed: _load, child: const Text('Coba lagi')),
      ],
    ),
  );

  Widget _footer(JsonMap meta) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Divider(),
      const SizedBox(height: 14),
      Text(
        meta['partial'] == true
            ? 'Cache terakhir: ${_date(meta['fetched_at'])}  •  refresh mingguan dimatikan'
            : 'Snapshot: ${_date(meta['fetched_at'])}  •  berikutnya: ${_date(meta['next_refresh_at'])}',
        style: const TextStyle(color: _muted, fontSize: 11),
      ),
      if (meta['last_error'] != null)
        Text('Refresh: ${meta['last_error']}', style: const TextStyle(color: Colors.amber, fontSize: 11)),
      const SizedBox(height: 5),
      const Text(
        'Skor = menang / (menang + kalah). Riset relatif berbasis snapshot; bukan rekomendasi investasi.',
        style: TextStyle(color: _muted, fontSize: 11),
      ),
    ],
  );

  Widget _browse() {
    final query = _search.text.trim().toLowerCase();
    final rankQuery = int.tryParse(query.replaceFirst('#', ''));
    var rows = (_data['items'] as List? ?? [])
        .map(asMap)
        .where(
          (r) => query.isEmpty ||
              (rankQuery != null
                  ? asInt(r['overall_rank']) == rankQuery
                  : '${r['ticker']} ${r['company_name']}'.toLowerCase().contains(query)),
        )
        .toList();
    rows.sort((a, b) {
      final av = (a['score'] as num?)?.toDouble() ?? -1;
      final bv = (b['score'] as num?)?.toDouble() ?? -1;
      return _descending ? bv.compareTo(av) : av.compareTo(bv);
    });
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 10,
          runSpacing: 2,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            const Text(
              'BROWSE FINGERPRINTS',
              style: TextStyle(
                color: _accent,
                fontSize: 12,
                letterSpacing: 1.05,
                fontWeight: FontWeight.w800,
              ),
            ),
            TextButton.icon(
              onPressed: () => setState(() => _descending = !_descending),
              icon: Icon(_descending ? Icons.south : Icons.north, size: 15),
              label: const Text('Win rate'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (rows.isEmpty)
          _panel(
            const Text(
              'Belum ada saham yang cocok. Pencarian ini hanya membaca CSV/cache lokal dan tidak memakai kredit API.',
            ),
          ),
        LayoutBuilder(
          builder: (context, constraints) {
            final mobile = constraints.maxWidth < 680;
            return Column(
              children: [
                if (!mobile)
                  const Padding(
                    padding: EdgeInsets.fromLTRB(10, 0, 10, 10),
                    child: Row(
                      children: [
                        SizedBox(width: 58, child: Text('RANK', style: TextStyle(color: _muted, fontSize: 11))),
                        Expanded(flex: 3, child: Text('TICKER', style: TextStyle(color: _muted, fontSize: 11))),
                        Expanded(flex: 2, child: Text('DUEL WIN RATE', style: TextStyle(color: _muted, fontSize: 11))),
                        Expanded(flex: 2, child: Text('DOMINANT SEGMENT', style: TextStyle(color: _muted, fontSize: 11))),
                        Expanded(child: Text('COVERAGE', style: TextStyle(color: _muted, fontSize: 11))),
                      ],
                    ),
                  ),
                for (final row in rows)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Material(
                      color: _surface,
                      borderRadius: BorderRadius.circular(12),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(12),
                        onTap: () => _open('${row['ticker']}'),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
                          decoration: BoxDecoration(
                            border: Border.all(color: _border),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: mobile ? _mobileStockRow(row) : _desktopStockRow(row),
                        ),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }

  Widget _desktopStockRow(JsonMap row) {
    final score = asDouble(row['score']);
    final coverage = ((asDouble(row['coverage']) ?? 0) * 100).clamp(0, 100);
    final axis = '${row['dominant_axis'] ?? 'Insufficient data'}';
    final color = _axisColor(axis);
    final rank = asInt(row['overall_rank']);
    return Row(
      children: [
        SizedBox(
          width: 58,
          child: Text(rank > 0 ? '#$rank' : '—', style: TextStyle(color: rank > 0 && rank <= 3 ? _accent : _muted, fontWeight: FontWeight.w800)),
        ),
        Expanded(
          flex: 3,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('${row['ticker']}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
              Text('${row['company_name'] ?? ''}', overflow: TextOverflow.ellipsis, style: const TextStyle(color: _muted, fontSize: 12)),
            ],
          ),
        ),
        Expanded(
          flex: 2,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _score(score, 22),
              const SizedBox(height: 7),
              SizedBox(width: 130, child: _animatedBar((score ?? 0) / 100, color)),
            ],
          ),
        ),
        Expanded(flex: 2, child: Align(alignment: Alignment.centerLeft, child: _pill(axis, color))),
        Expanded(
          child: Text(
            '${coverage.toStringAsFixed(0)}%',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
        ),
      ],
    );
  }

  Widget _mobileStockRow(JsonMap row) {
    final score = asDouble(row['score']);
    final axis = '${row['dominant_axis'] ?? 'Insufficient data'}';
    final rank = asInt(row['overall_rank']);
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (rank > 0) Text('#$rank  ', style: TextStyle(color: rank <= 3 ? _accent : _muted, fontWeight: FontWeight.w800)),
                  Text('${row['ticker']}', style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
                ],
              ),
              Text('${row['company_name'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: _muted, fontSize: 12)),
              const SizedBox(height: 9),
              _pill(axis, _axisColor(axis)),
            ],
          ),
        ),
        const SizedBox(width: 12),
        _score(score, 25),
        const SizedBox(width: 4),
        const Icon(Icons.chevron_right_rounded, color: _muted),
      ],
    );
  }

  Widget _detail(JsonMap p) {
    final benchmark = asMap(p['benchmark']);
    final stock = asMap(p['stock']);
    final axes = asMap(p['axes']);
    final opponents = (p['opponents'] as num?)?.toDouble() ?? 0;
    final dominantName = '${p['dominant_axis'] ?? ''}'.split(' / ').first;
    final dominantData = asMap(axes[dominantName]);
    final pe = (stock['pe_ttm'] as num?)?.toDouble();
    final median = (benchmark['pe_median'] as num?)?.toDouble();
    return Column(
      key: ValueKey('detail-${p['ticker']}'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            TextButton.icon(
              onPressed: _goHome,
              icon: const Icon(Icons.arrow_back_rounded, size: 17),
              label: const Text('All stocks'),
            ),
            const Spacer(),
            FilledButton.icon(
              onPressed: () => _openCompare('${p['ticker']}'),
              icon: const Icon(Icons.compare_arrows_rounded, size: 18),
              label: const Text('Compare'),
              style: FilledButton.styleFrom(
                backgroundColor: _accent,
                foregroundColor: _bg,
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
              ),
            ),
          ],
        ),
        const SizedBox(height: 22),
        Text(
          '${p['ticker']}',
          style: const TextStyle(
            fontSize: 46,
            fontWeight: FontWeight.w800,
            letterSpacing: -2,
          ),
        ),
        Text(
          '${p['company_name'] ?? ''}  ·  ${p['sector'] ?? ''} / ${p['sub_sector'] ?? ''}',
          style: const TextStyle(color: _muted),
        ),
        const SizedBox(height: 24),
        LayoutBuilder(
          builder: (context, c) {
            final cards = [
              _panel(
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'DUEL WIN RATE',
                      style: TextStyle(
                        color: _muted,
                        fontSize: 11,
                        letterSpacing: 1.3,
                      ),
                    ),
                    const SizedBox(height: 14),
                    _score(p['score'], 54),
                    Text(
                      '${p['wins']} menang · ${p['losses']} kalah · ${p['draws']} seri',
                    ),
                    Text(
                      '${p['unavailable']} tidak cukup data / ${p['opponents']} lawan',
                      style: const TextStyle(color: _muted, fontSize: 12),
                    ),
                  ],
                ),
              ),
              _panel(
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'DOMINANT SEGMENT',
                      style: TextStyle(
                        color: _muted,
                        fontSize: 11,
                        letterSpacing: 1.3,
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      '${p['dominant_axis'] ?? 'Belum tersedia'}',
                      style: const TextStyle(
                        fontSize: 27,
                        color: _accent,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (asInt(dominantData['rank']) > 0) ...[
                      const SizedBox(height: 5),
                      Text(
                        'Top ${asInt(dominantData['rank'])} in $dominantName',
                        style: const TextStyle(color: _accent, fontWeight: FontWeight.w700),
                      ),
                    ],
                    const SizedBox(height: 12),
                    Text(
                      'Duel dengan data cukup: ${(((p['coverage'] as num?) ?? 0) * 100).toStringAsFixed(0)}%',
                      style: const TextStyle(color: _muted),
                    ),
                  ],
                ),
              ),
            ];
            return c.maxWidth < 620
                ? Column(
                    children: [cards[0], const SizedBox(height: 12), cards[1]],
                  )
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: cards[0]),
                      const SizedBox(width: 16),
                      Expanded(child: cards[1]),
                    ],
                  );
          },
        ),
        const SizedBox(height: 24),
        _panel(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Where the wins came from',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
              ),
              const Text(
                'Kemenangan per segmen; satu duel dapat menang di beberapa segmen.',
                style: TextStyle(color: _muted, fontSize: 12),
              ),
              const SizedBox(height: 22),
              for (final entry in axes.entries)
                Padding(
                  padding: const EdgeInsets.only(bottom: 20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(entry.key, style: const TextStyle(fontWeight: FontWeight.w700)),
                                const SizedBox(height: 3),
                                Text(
                                  '${asMap(entry.value)['explanation'] ?? ''}',
                                  style: const TextStyle(color: _muted, fontSize: 11),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 12),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              if (asInt(asMap(entry.value)['rank']) > 0)
                                Text(
                                  'Top ${asInt(asMap(entry.value)['rank'])} in ${entry.key}',
                                  style: const TextStyle(color: _accent, fontWeight: FontWeight.w700),
                                ),
                              Text(
                                '${asMap(entry.value)['wins']} / ${p['opponents']}',
                                style: const TextStyle(color: _accent),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 5),
                      Align(
                        alignment: Alignment.centerRight,
                        child: Wrap(
                          spacing: 5,
                          children: [
                            if (asMapList(asMap(entry.value)['ranks_above']).isNotEmpty)
                              _rankNeighborMenu('Ranks above', asMapList(asMap(entry.value)['ranks_above']), _accent),
                            if (asMapList(asMap(entry.value)['ranks_below']).isNotEmpty)
                              _rankNeighborMenu('Ranks below', asMapList(asMap(entry.value)['ranks_below']), _muted),
                          ],
                        ),
                      ),
                      const SizedBox(height: 9),
                      TweenAnimationBuilder<double>(
                        duration: const Duration(milliseconds: 800),
                        curve: Curves.easeOutCubic,
                        tween: Tween<double>(
                          begin: 0,
                          end: opponents > 0
                              ? (((asMap(entry.value)['wins'] as num?) ?? 0) / opponents)
                              : 0,
                        ),
                        builder: (_, value, child) => ClipRRect(
                          borderRadius: BorderRadius.circular(5),
                          child: LinearProgressIndicator(
                            value: value.clamp(0.0, 1.0).toDouble(),
                            minHeight: 9,
                            color: _axisColor(entry.key),
                            backgroundColor: _border,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        _panel(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'What this means',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 12),
              Text('${p['meaning']}'),
            ],
          ),
        ),
        const SizedBox(height: 18),
        _panel(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'P/E · sector evidence',
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 10),
              Text('${benchmark['sector']} → ${benchmark['sub_sector']}'),
              const SizedBox(height: 12),
              Text(
                '${_num(pe)}x ÷ ${_num(median)}x = ${_num(pe != null && pe > 0 && median != null && median > 0 ? pe / median : null)}x',
                style: const TextStyle(
                  color: _accent,
                  fontSize: 25,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                'P/E saham / filtered median subsektor · ${benchmark['total_companies'] ?? '—'} perusahaan',
              ),
              const Text(
                'Jumlah sampel P/E setelah filter tidak disediakan Sectors.',
                style: TextStyle(color: _muted, fontSize: 12),
              ),
              Text(
                'Diambil: ${_date(benchmark['fetched_at'])}',
                style: const TextStyle(color: _muted, fontSize: 12),
              ),
              const SizedBox(height: 12),
              const Text(
                'Sesama subsektor: P/E mentah. Beda subsektor: P/E relatif. P/E negatif atau nol tidak dinilai murah.',
                style: TextStyle(color: _muted),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        ExpansionTile(
          title: const Text('15-feature evidence'),
          tilePadding: EdgeInsets.zero,
          children: [
            for (final raw in p['features'] as List? ?? [])
              Builder(
                builder: (_) {
                  final f = asMap(raw);
                  return ListTile(
                    title: Text('${f['number']}. ${f['label']}'),
                    subtitle: Text(
                      '${f['segment']} · ${f['basis']}\nRaw: ${f['raw'] ?? 'N/A'} · Baseline: ${f['baseline'] ?? 'N/A'}',
                    ),
                    trailing: Text(
                      _num(f['value'] as num?),
                      style: const TextStyle(color: _accent),
                    ),
                  );
                },
              ),
          ],
        ),
        ExpansionTile(
          title: const Text('Data limitations'),
          tilePadding: EdgeInsets.zero,
          children: [
            for (final note in p['limitations'] as List? ?? [])
              ListTile(
                leading: const Icon(Icons.info_outline, size: 18),
                title: Text('$note'),
              ),
            for (final flag in stock['red_flags'] as List? ?? [])
              ListTile(
                leading: const Icon(Icons.flag_outlined, color: Colors.amber),
                title: Text('${asMap(flag)['message']}'),
              ),
          ],
        ),
      ],
    );
  }

  Widget _rankNeighborMenu(String label, List<JsonMap> rows, Color color) {
    return PopupMenuButton<void>(
      tooltip: label,
      itemBuilder: (_) => _rankNeighborMenuItems(rows, color),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: color.withAlpha(12),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: color.withAlpha(100)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(label, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w700)),
            const SizedBox(width: 2),
            Icon(Icons.arrow_drop_down_rounded, size: 16, color: color),
          ],
        ),
      ),
    );
  }

  List<PopupMenuEntry<void>> _rankNeighborMenuItems(List<JsonMap> rows, Color color) => rows
      .map<PopupMenuEntry<void>>(
        (row) => PopupMenuItem<void>(
          enabled: false,
          child: Row(
            children: [
              SizedBox(
                width: 42,
                child: Text('#${asInt(row['rank'])}', style: TextStyle(color: color, fontWeight: FontWeight.w800)),
              ),
              Text('${row['ticker']}', style: const TextStyle(fontWeight: FontWeight.w700)),
            ],
          ),
        ),
      )
      .toList();

  Widget _sectorDirectory() {
    final groups = <String, List<JsonMap>>{};
    for (final r in _sectors) {
      groups.putIfAbsent('${r['sector']}', () => []).add(r);
    }
    return Column(
      key: const ValueKey('sectors'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextButton.icon(
          onPressed: _goHome,
          icon: const Icon(Icons.arrow_back_rounded, size: 17),
          label: const Text('Back to home'),
        ),
        const SizedBox(height: 20),
        const Text(
          'Indonesia Economic Sectors',
          style: TextStyle(fontSize: 30, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 12),
        const Text(
          'Benchmark P/E per subsektor IDX-IC. Dibaca dari snapshot mingguan.',
          style: TextStyle(color: _muted),
        ),
        const SizedBox(height: 24),
        if (groups.isEmpty)
          const Text(
            'Belum ada benchmark. Tunggu pengambilan mingguan pertama.',
          ),
        LayoutBuilder(
          builder: (context, c) {
            final columns = c.maxWidth > 850
                ? 3
                : c.maxWidth > 550
                ? 2
                : 1;
            return Wrap(
              spacing: 18,
              runSpacing: 18,
              children: [
                for (final entry in groups.entries)
                  SizedBox(
                    width: (c.maxWidth - (columns - 1) * 18) / columns,
                    child: _panel(
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            Icons.account_tree_outlined,
                            color: _accent,
                            size: 22,
                          ),
                          const SizedBox(height: 12),
                          Text(
                            entry.key,
                            style: const TextStyle(
                              fontSize: 19,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            '${entry.value.length} subsektor',
                            style: const TextStyle(color: _muted, fontSize: 12),
                          ),
                          const SizedBox(height: 18),
                          for (final r in entry.value)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '${r['sub_sector']}',
                                    style: const TextStyle(
                                      decoration: TextDecoration.underline,
                                    ),
                                  ),
                                  Text(
                                    'Median P/E ${r['filtered_median_pe'] == '' ? 'N/A' : _num(num.tryParse('${r['filtered_median_pe']}'))}x · ${r['total_companies']} perusahaan',
                                    style: const TextStyle(
                                      color: _muted,
                                      fontSize: 12,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }

  Widget _panel(Widget child) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(22),
    decoration: BoxDecoration(
      color: _surface,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: _border),
    ),
    child: child,
  );
  Widget _tag(String text, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
    decoration: BoxDecoration(
      border: Border.all(color: color.withAlpha(90)),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      text,
      style: TextStyle(
        color: color,
        fontSize: 10,
        fontWeight: FontWeight.w600,
        letterSpacing: 1,
      ),
      ),
    );
  Widget _pill(String text, Color color) => Container(
    constraints: const BoxConstraints(maxWidth: 210),
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
    decoration: BoxDecoration(
      color: color.withAlpha(12),
      border: Border.all(color: color),
      borderRadius: BorderRadius.circular(999),
    ),
    child: Text(
      text,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700),
    ),
  );
  Widget _animatedBar(double rawValue, Color color) => TweenAnimationBuilder<double>(
    duration: const Duration(milliseconds: 720),
    curve: Curves.easeOutCubic,
    tween: Tween(begin: 0, end: rawValue.clamp(0.0, 1.0).toDouble()),
    builder: (_, value, child) => ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: LinearProgressIndicator(
        value: value,
        minHeight: 8,
        backgroundColor: _border,
        color: color,
      ),
    ),
  );
  Color _axisColor(String value) {
    final axis = value.toLowerCase();
    if (axis.contains('growth')) return const Color(0xFFF2C35F);
    if (axis.contains('financial')) return _green;
    if (axis.contains('performance')) return const Color(0xFFB98BFF);
    if (axis.contains('dividend')) return const Color(0xFF7DDDB6);
    if (axis.contains('valuation')) return _accent;
    return _muted;
  }
  Widget _score(dynamic value, double size) => value is num
      ? TweenAnimationBuilder<double>(
          key: ValueKey('$value/$size'),
          tween: Tween(begin: 0, end: value.toDouble()),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          builder: (_, number, child) => Text(
            '${number.toStringAsFixed(1)}%',
            style: TextStyle(
              fontSize: size,
              color: _green,
              fontWeight: FontWeight.w600,
            ),
          ),
        )
      : Text(
          '—',
          style: TextStyle(fontSize: size, color: _muted),
        );
  String _num(num? value) => value?.toStringAsFixed(2) ?? '—';
  String _date(dynamic value) => value == null
      ? 'Belum tersedia'
      : '${DateTime.tryParse('$value')?.toLocal() ?? value}'.split('.').first;
}
