import 'package:flutter/material.dart';

import '../models/duel_models.dart';
import '../services/duel_api.dart';

const _bg = Color(0xFFFFFFFF);
const _surface = Color(0xFFFFFFFF);
const _surfaceSoft = Color(0xFFF7F8FA);
const _border = Color(0xFFE0E4EA);
const _accent = Color(0xFF7156D9);
const _muted = Color(0xFF626B7C);
const _green = Color(0xFF24A77A);
const _amber = Color(0xFFC47A00);

class CompareScreen extends StatefulWidget {
  const CompareScreen({
    super.key,
    required this.api,
    required this.stocks,
    required this.onBack,
    this.initialTicker,
    this.initialTickerB,
  });

  final DuelApi api;
  final List<JsonMap> stocks;
  final VoidCallback onBack;
  final String? initialTicker;
  final String? initialTickerB;

  @override
  State<CompareScreen> createState() => _CompareScreenState();
}

class _CompareScreenState extends State<CompareScreen> {
  late final TextEditingController _tickerA;
  late final TextEditingController _tickerB;
  final _focusA = FocusNode();
  final _focusB = FocusNode();
  DuelReport? _report;
  String? _error;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _tickerA = TextEditingController(text: widget.initialTicker ?? '');
    _tickerB = TextEditingController(text: widget.initialTickerB ?? '');
  }

  @override
  void dispose() {
    _tickerA.dispose();
    _tickerB.dispose();
    _focusA.dispose();
    _focusB.dispose();
    super.dispose();
  }

  String _clean(String value) => value.trim().toUpperCase().replaceAll('.JK', '');

  void _swap() {
    final previousA = _tickerA.text;
    _tickerA.text = _tickerB.text;
    _tickerB.text = previousA;
    setState(() {
      _report = null;
      _error = null;
    });
  }

  Future<void> _run() async {
    final a = _clean(_tickerA.text);
    final b = _clean(_tickerB.text);
    if (a.length < 2 || b.length < 2 || a == b) {
      setState(() => _error = 'Isi dua ticker berbeda yang tersedia di cache.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await widget.api.runDuel(
        tickerA: a,
        tickerB: b,
        forceRefresh: false,
        maxNewCredits: 0,
      );
      if (!mounted) return;
      setState(() => _report = result);
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextButton.icon(
          onPressed: widget.onBack,
          icon: const Icon(Icons.arrow_back_rounded, size: 17),
          label: const Text('Back'),
        ),
        const SizedBox(height: 20),
        const Text(
          'Compare fingerprints.',
          style: TextStyle(
            fontSize: 38,
            height: 1.08,
            fontWeight: FontWeight.w800,
            letterSpacing: -1.2,
          ),
        ),
        const SizedBox(height: 9),
        const Text(
          'Duel dua saham memakai 15 fitur dan aturan normalisasi subsektor. Semua perhitungan membaca CSV lokal.',
          style: TextStyle(color: _muted, fontSize: 15),
        ),
        const SizedBox(height: 24),
        _selector(),
        if (_loading)
          const Padding(
            padding: EdgeInsets.only(top: 18),
            child: LinearProgressIndicator(minHeight: 2),
          ),
        if (_error != null) ...[
          const SizedBox(height: 16),
          _panel(
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.warning_amber_rounded, color: _amber),
                const SizedBox(width: 10),
                Expanded(child: Text(_error!, style: const TextStyle(color: _amber))),
              ],
            ),
          ),
        ],
        if (_report != null) ...[
          const SizedBox(height: 26),
          _result(_report!),
        ],
      ],
    );
  }

  Widget _selector() {
    final rankedStocks = [...widget.stocks]
      ..sort((a, b) => (asDouble(b['score']) ?? -1).compareTo(asDouble(a['score']) ?? -1));
    return _panel(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          LayoutBuilder(
            builder: (context, constraints) {
              final fields = [
                _tickerField('STOCK A', _tickerA, _focusA),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 18),
                  child: Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: _accent.withAlpha(20),
                      shape: BoxShape.circle,
                      border: Border.all(color: _accent.withAlpha(100)),
                    ),
                    child: IconButton(
                      tooltip: 'Swap stocks',
                      padding: EdgeInsets.zero,
                      onPressed: _swap,
                      icon: const Icon(Icons.swap_horiz_rounded, color: _accent, size: 20),
                    ),
                  ),
                ),
                _tickerField('STOCK B', _tickerB, _focusB),
              ];
              return constraints.maxWidth < 650
                  ? Column(
                      children: [
                        fields[0],
                        fields[1],
                        fields[2],
                      ],
                    )
                  : Row(
                      children: [
                        Expanded(child: fields[0]),
                        fields[1],
                        Expanded(child: fields[2]),
                      ],
                    );
            },
          ),
          if (rankedStocks.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('TOP COMPANIES AVAILABLE IN CACHE', style: TextStyle(color: _muted, fontSize: 10, letterSpacing: 1)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 7,
              runSpacing: 7,
              children: [
                for (final row in rankedStocks.take(12))
                  ActionChip(
                    label: Text(
                      '${row['ticker']}  ${asDouble(row['score']) == null ? '' : '${asDouble(row['score'])!.toStringAsFixed(0)}%'}',
                    ),
                    onPressed: () {
                      setState(() {
                        _report = null;
                        _error = null;
                      });
                      if (_tickerA.text.trim().isEmpty) {
                        _tickerA.text = '${row['ticker']}';
                        _focusB.requestFocus();
                      } else {
                        _tickerB.text = '${row['ticker']}';
                      }
                    },
                    backgroundColor: _surfaceSoft,
                    side: const BorderSide(color: _border),
                  ),
              ],
            ),
          ],
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _loading ? null : _run,
              icon: const Icon(Icons.bolt_rounded),
              label: const Text('Run local duel'),
              style: FilledButton.styleFrom(
                backgroundColor: _accent,
                foregroundColor: _bg,
                padding: const EdgeInsets.symmetric(vertical: 17),
                textStyle: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
          ),
          const SizedBox(height: 8),
          const Center(
            child: Text('0 provider credits · no live refresh', style: TextStyle(color: _muted, fontSize: 11)),
          ),
        ],
      ),
    );
  }

  Iterable<JsonMap> _tickerOptions(TextEditingValue value) {
    final query = value.text.trim().toLowerCase();
    final rankQuery = int.tryParse(query.replaceFirst('#', ''));
    final rows = widget.stocks.where((row) {
      if (query.isEmpty) return true;
      if (rankQuery != null) return asInt(row['overall_rank']) == rankQuery;
      return '${row['ticker']} ${row['company_name']}'.toLowerCase().contains(query);
    }).toList()
      ..sort((a, b) => (asDouble(b['score']) ?? -1).compareTo(asDouble(a['score']) ?? -1));
    return rows.take(8);
  }

  Widget _tickerField(
    String label,
    TextEditingController controller,
    FocusNode focusNode,
  ) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(label, style: const TextStyle(color: _muted, fontSize: 10, letterSpacing: 1)),
      const SizedBox(height: 7),
      RawAutocomplete<JsonMap>(
        textEditingController: controller,
        focusNode: focusNode,
        displayStringForOption: (row) => '${row['ticker']}',
        optionsBuilder: _tickerOptions,
        onSelected: (row) {
          controller.text = '${row['ticker']}';
          setState(() {
            _report = null;
            _error = null;
          });
          if (identical(controller, _tickerA)) _focusB.requestFocus();
        },
        fieldViewBuilder: (context, textController, fieldFocus, onSubmitted) => TextField(
          controller: textController,
          focusNode: fieldFocus,
          onChanged: (_) => setState(() {
            _report = null;
            _error = null;
          }),
          onSubmitted: (_) => onSubmitted(),
          textCapitalization: TextCapitalization.characters,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
          decoration: InputDecoration(
            hintText: 'Pilih ticker',
            prefixIcon: const Icon(Icons.search_rounded, size: 19),
            filled: true,
            fillColor: _surfaceSoft,
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: _border),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: _accent),
            ),
          ),
        ),
        optionsViewBuilder: (context, onSelected, options) {
          final rows = options.toList(growable: false);
          return Align(
            alignment: Alignment.topLeft,
            child: Material(
              color: Colors.transparent,
              elevation: 12,
              child: Container(
                width: MediaQuery.of(context).size.width < 390
                    ? MediaQuery.of(context).size.width - 48
                    : 330,
                constraints: const BoxConstraints(maxHeight: 340),
                padding: const EdgeInsets.all(7),
                decoration: BoxDecoration(
                  color: _surfaceSoft,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: _accent.withAlpha(100)),
                ),
                child: ListView.builder(
                  shrinkWrap: true,
                  padding: EdgeInsets.zero,
                  itemCount: rows.length,
                  itemBuilder: (itemContext, index) {
                    final row = rows[index];
                    final highlighted = AutocompleteHighlightedOption.of(itemContext) == index;
                    return Material(
                      // Use an opaque Material: this avoids the ListTile
                      // splash assertion and keeps an option tappable before
                      // the text field gives up focus on web.
                      color: highlighted ? _accent.withAlpha(24) : _surfaceSoft,
                      child: GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onTapDown: (_) => onSelected(row),
                        child: ListTile(
                          dense: true,
                          // Preserve a semantic tap action for keyboard and
                          // assistive technologies. Pointer selection happens
                          // in onTapDown so the overlay cannot vanish first.
                          onTap: () => onSelected(row),
                          leading: Text(
                            asInt(row['overall_rank']) > 0 ? '#${asInt(row['overall_rank'])}' : '—',
                            style: const TextStyle(color: _accent, fontWeight: FontWeight.w800),
                          ),
                          title: Text('${row['ticker']}', style: const TextStyle(fontWeight: FontWeight.w800)),
                          subtitle: Text('${row['company_name'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis),
                          trailing: Text(
                            asDouble(row['score']) == null ? 'N/A' : '${asDouble(row['score'])!.toStringAsFixed(1)}%',
                            style: const TextStyle(color: _green, fontWeight: FontWeight.w800),
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
          );
        },
      ),
    ],
  );

  Widget _result(DuelReport report) {
    final intelligence = report.intelligence;
    final confidence = asMap(intelligence['confidence']);
    final verdictColor = report.available ? _green : _amber;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _panel(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  _badge('${report.tickerA}  VS  ${report.tickerB}', _accent),
                  _badge('CONFIDENCE ${confidence['level'] ?? 'N/A'}'.toString().toUpperCase(), verdictColor),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                report.available
                    ? report.winner == 'draw'
                          ? 'Segment-balanced · ${report.featurePointShare(report.tickerA).toStringAsFixed(1)}% / ${report.featurePointShare(report.tickerB).toStringAsFixed(1)}%'
                          : '${report.winner} leads · ${report.featurePointShare(report.winner).toStringAsFixed(1)}%'
                    : 'Verdict withheld',
                style: TextStyle(fontSize: 32, fontWeight: FontWeight.w800, color: verdictColor),
              ),
              const SizedBox(height: 8),
              Text('${intelligence['headline'] ?? report.narrative}', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Text('${intelligence['executive_summary'] ?? ''}', style: const TextStyle(color: _muted)),
              const SizedBox(height: 22),
              _continuousScore(report),
            ],
          ),
        ),
        const SizedBox(height: 18),
        _segmentGrid(report),
        const SizedBox(height: 18),
        _reasoning(intelligence),
        const SizedBox(height: 12),
        _featureEvidence(report),
      ],
    );
  }

  Widget _continuousScore(DuelReport report) {
    final a = report.featurePointShare(report.tickerA).clamp(0, 100);
    final b = report.featurePointShare(report.tickerB).clamp(0, 100);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surfaceSoft,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: _scoreLabel(report.tickerA, a, TextAlign.left)),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 10),
                child: Text('FEATURE\nPOINT SHARE', textAlign: TextAlign.center, style: TextStyle(color: _muted, fontSize: 9, letterSpacing: .8)),
              ),
              Expanded(child: _scoreLabel(report.tickerB, b, TextAlign.right)),
            ],
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(99),
            child: SizedBox(
              height: 10,
              child: Row(
                children: [
                  Expanded(flex: (a * 100).round().clamp(1, 9999).toInt(), child: Container(color: _accent)),
                  Expanded(flex: (b * 100).round().clamp(1, 9999).toInt(), child: Container(color: _green)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 9),
          Text(
            '${asInt(report.verdict['valid_features'], report.features.length)} fitur valid · seri 0,5 · margin tilt maks. ±0,45 poin · data hilang tidak dihitung',
            style: const TextStyle(color: _muted, fontSize: 10),
          ),
        ],
      ),
    );
  }

  Widget _scoreLabel(String ticker, num score, TextAlign align) => Column(
    crossAxisAlignment: align == TextAlign.left ? CrossAxisAlignment.start : CrossAxisAlignment.end,
    children: [
      Text(ticker, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
      Text('${score.toStringAsFixed(1)}%', textAlign: align, style: const TextStyle(fontSize: 30, height: 1.05, fontWeight: FontWeight.w800)),
    ],
  );

  Widget _segmentGrid(DuelReport report) => LayoutBuilder(
    builder: (context, constraints) {
      final columns = constraints.maxWidth >= 900 ? 5 : constraints.maxWidth >= 560 ? 2 : 1;
      final width = (constraints.maxWidth - (columns - 1) * 12) / columns;
      return Wrap(
        spacing: 12,
        runSpacing: 12,
        children: [
          for (final segment in report.segments)
            SizedBox(
              width: width,
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: _surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: _segmentMissingFeatureCount(report, segment) > 0
                        ? _amber.withAlpha(120)
                        : _border,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${segment['segment']}', style: const TextStyle(color: _muted, fontSize: 11)),
                    const SizedBox(height: 11),
                    Row(
                      children: [
                        Expanded(child: Text(report.tickerA, style: const TextStyle(fontWeight: FontWeight.w700))),
                        Text('${_segmentShare(segment, true).toStringAsFixed(1)}%', style: TextStyle(color: _segmentColor('${segment['segment']}'), fontWeight: FontWeight.w800)),
                      ],
                    ),
                    const SizedBox(height: 6),
                    _splitBar(_segmentShare(segment, true), _segmentColor('${segment['segment']}')),
                    const SizedBox(height: 7),
                    Row(
                      children: [
                        Expanded(child: Text(report.tickerB, style: const TextStyle(fontWeight: FontWeight.w700))),
                        Text('${_segmentShare(segment, false).toStringAsFixed(1)}%', style: const TextStyle(color: _muted, fontWeight: FontWeight.w800)),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '${segment['winner'] == 'draw' ? 'Balanced' : '${segment['winner']} leads'} '
                      '· ${_segmentValidFeatureCount(report, segment)} valid '
                      '· ${segment['draws']} draw',
                      style: const TextStyle(color: _muted, fontSize: 10),
                    ),
                    if (_segmentMissingFeatureCount(report, segment) > 0) ...[
                      const SizedBox(height: 5),
                      Theme(
                        data: Theme.of(context).copyWith(
                          dividerColor: Colors.transparent,
                        ),
                        child: ExpansionTile(
                          key: Key('missing-${segment['segment']}'),
                          tilePadding: EdgeInsets.zero,
                          childrenPadding: const EdgeInsets.only(bottom: 5),
                          minTileHeight: 34,
                          leading: const Icon(
                            Icons.warning_amber_rounded,
                            size: 17,
                            color: _amber,
                          ),
                          title: Text(
                            '${_segmentMissingFeatureCount(report, segment)} missing '
                            '${_segmentMissingFeatureCount(report, segment) == 1 ? 'feature' : 'features'}',
                            style: const TextStyle(
                              color: _amber,
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          subtitle: const Text(
                            'Excluded from the percentage',
                            style: TextStyle(color: _muted, fontSize: 9),
                          ),
                          children: [
                            Padding(
                              padding: const EdgeInsets.only(left: 4, bottom: 7),
                              child: Text(
                                _missingWarningText(report, segment),
                                style: const TextStyle(color: _muted, fontSize: 10),
                              ),
                            ),
                            for (final feature in _missingFeatures(
                              report,
                              '${segment['segment']}',
                            ))
                              Container(
                                width: double.infinity,
                                padding: const EdgeInsets.symmetric(vertical: 5),
                                decoration: const BoxDecoration(
                                  border: Border(
                                    top: BorderSide(color: _border),
                                  ),
                                ),
                                child: Text(
                                  '${feature['number']}. ${feature['label']} · '
                                  '${_missingSide(report, feature)}',
                                  style: const TextStyle(
                                    color: _amber,
                                    fontSize: 10,
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
        ],
      );
    },
  );

  String _missingWarningText(DuelReport report, JsonMap segment) =>
      '${_segmentMissingFeatureCount(report, segment)} fitur tidak memiliki pasangan data lengkap. '
      'Fitur tersebut tetap ditampilkan sebagai missing, tetapi tidak masuk denominator. ';

  List<JsonMap> _missingFeatures(DuelReport report, String segment) => report.features
      .where(
        (feature) =>
            '${feature['segment']}' == segment &&
            (feature['value_a'] == null ||
                feature['value_b'] == null ||
                const {'missing_data', 'invalid_value', 'both_invalid'}
                    .contains('${feature['reason']}')),
      )
      .toList(growable: false);

  String _missingSide(DuelReport report, JsonMap feature) {
    final aMissing = feature['value_a'] == null;
    final bMissing = feature['value_b'] == null;
    if (aMissing && bMissing) return '${report.tickerA} & ${report.tickerB} missing';
    if (aMissing) return '${report.tickerA} missing';
    if (bMissing) return '${report.tickerB} missing';
    return 'comparison pair incomplete';
  }

  int _segmentMissingFeatureCount(DuelReport report, JsonMap segment) {
    final declared = asInt(segment['missing_features']);
    final detected = _missingFeatures(report, '${segment['segment']}').length;
    return declared > detected ? declared : detected;
  }

  int _segmentValidFeatureCount(DuelReport report, JsonMap segment) {
    final total = report.features
        .where((feature) => '${feature['segment']}' == '${segment['segment']}')
        .length;
    return (total - _segmentMissingFeatureCount(report, segment))
        .clamp(0, total)
        .toInt();
  }

  double _segmentShare(JsonMap segment, bool stockA) {
    final direct = asDouble(segment[stockA ? 'point_share_a' : 'point_share_b']);
    if (direct != null) return direct.clamp(0, 100).toDouble();
    final wins = asInt(segment[stockA ? 'wins_a' : 'wins_b']);
    final draws = asInt(segment['draws']);
    final valid = wins + asInt(segment[stockA ? 'wins_b' : 'wins_a']) + draws;
    return valid == 0 ? 0 : 100 * (wins + draws * .5) / valid;
  }

  Widget _splitBar(double share, Color color) => ClipRRect(
    borderRadius: BorderRadius.circular(99),
    child: SizedBox(
      height: 6,
      child: Row(
        children: [
          Expanded(flex: (share * 100).round().clamp(1, 9999).toInt(), child: Container(color: color)),
          Expanded(flex: ((100 - share) * 100).round().clamp(1, 9999).toInt(), child: Container(color: _border)),
        ],
      ),
    ),
  );

  Widget _reasoning(JsonMap intelligence) {
    final drivers = asMapList(intelligence['segment_drivers']);
    final risks = asMapList(intelligence['risk_watch']);
    return _panel(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('MARKET INTELLIGENCE REASONING', style: TextStyle(color: _accent, fontSize: 12, letterSpacing: 1, fontWeight: FontWeight.w800)),
          const SizedBox(height: 14),
          Text('${intelligence['tradeoff'] ?? ''}', style: const TextStyle(fontSize: 15)),
          const SizedBox(height: 12),
          Text('${intelligence['comparison_logic'] ?? ''}', style: const TextStyle(color: _muted)),
          if (drivers.isNotEmpty) ...[
            const SizedBox(height: 20),
            for (final driver in drivers)
              Padding(
                padding: const EdgeInsets.only(bottom: 13),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(width: 7, height: 7, margin: const EdgeInsets.only(top: 7), decoration: BoxDecoration(color: _segmentColor('${driver['segment']}'), shape: BoxShape.circle)),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${driver['title']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                          Text('${driver['insight']}', style: const TextStyle(color: _muted, fontSize: 12)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
          ],
          if (risks.isNotEmpty) ...[
            const Divider(height: 28),
            const Text('RISK WATCH', style: TextStyle(color: _amber, fontSize: 11, letterSpacing: 1, fontWeight: FontWeight.w800)),
            const SizedBox(height: 9),
            for (final risk in risks)
              Text('• ${risk['ticker']}: ${risk['message']}', style: const TextStyle(color: _amber, fontSize: 12)),
          ],
        ],
      ),
    );
  }

  Widget _featureEvidence(DuelReport report) => Container(
    decoration: BoxDecoration(
      color: _surface,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: _border),
    ),
    child: ExpansionTile(
      initiallyExpanded: true,
      title: const Text('15-feature duel evidence', style: TextStyle(fontWeight: FontWeight.w700)),
      subtitle: const Text('Angka kedua saham ditampilkan; kotak berwarna menandai pemenang fitur.', style: TextStyle(color: _muted, fontSize: 12)),
      children: [
        for (final feature in report.features)
          _featureRow(report, feature),
      ],
    ),
  );

  Widget _featureRow(DuelReport report, JsonMap feature) {
    final segment = '${feature['segment']}';
    final color = _segmentColor(segment);
    final winner = '${feature['winner']}';
    final missing = feature['value_a'] == null ||
        feature['value_b'] == null ||
        const {'missing_data', 'invalid_value', 'both_invalid'}
            .contains('${feature['reason']}');
    return Container(
      margin: const EdgeInsets.fromLTRB(14, 0, 14, 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _surfaceSoft,
        borderRadius: BorderRadius.circular(11),
        border: Border.all(color: _border),
      ),
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
                    Text('${feature['number']}. ${feature['label']}', style: const TextStyle(fontWeight: FontWeight.w800)),
                    const SizedBox(height: 3),
                    Text('$segment · ${_basisLabel(feature)}', style: const TextStyle(color: _muted, fontSize: 11)),
                  ],
                ),
              ),
              _badge(
                missing ? 'MISSING' : winner == 'draw' ? 'DRAW' : '$winner WINS',
                missing ? _amber : winner == 'draw' ? _muted : color,
              ),
            ],
          ),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, constraints) {
              final cards = [
                _featureValueCard(report.tickerA, feature, true, winner == report.tickerA, color),
                _featureValueCard(report.tickerB, feature, false, winner == report.tickerB, color),
              ];
              return constraints.maxWidth < 470
                  ? Column(children: [cards[0], const SizedBox(height: 8), cards[1]])
                  : Row(children: [Expanded(child: cards[0]), const SizedBox(width: 10), Expanded(child: cards[1])]);
            },
          ),
        ],
      ),
    );
  }

  Widget _featureValueCard(String ticker, JsonMap feature, bool stockA, bool won, Color color) {
    final suffix = stockA ? 'a' : 'b';
    final value = asDouble(feature['value_$suffix']);
    final raw = asDouble(feature['raw_value_$suffix']);
    final baseline = asDouble(feature['baseline_$suffix']);
    final basis = '${feature['comparison_basis'] ?? ''}';
    return AnimatedContainer(
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOutCubic,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: won ? color.withAlpha(22) : _surfaceSoft,
        borderRadius: BorderRadius.circular(9),
        border: Border.all(color: won ? color : _border, width: won ? 1.4 : 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(ticker, style: TextStyle(color: won ? color : _muted, fontWeight: FontWeight.w800))),
              if (won) Icon(Icons.check_circle_rounded, size: 15, color: color),
            ],
          ),
          const SizedBox(height: 8),
          Text(_formatFeatureValue('${feature['key']}', value, compared: true), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(
            _valueContext('${feature['key']}', raw, baseline, basis),
            style: const TextStyle(color: _muted, fontSize: 10),
          ),
        ],
      ),
    );
  }

  String _basisLabel(JsonMap feature) {
    if (feature['reason'] == 'missing_data') return 'data pair incomplete';
    if (feature['reason'] == 'invalid_value') return 'invalid value penalized';
    return '${feature['comparison_basis'] ?? feature['reason']}';
  }

  String _valueContext(String key, double? raw, double? baseline, String basis) {
    if (raw == null) return 'raw — · baseline ${_formatFeatureValue(key, baseline)}';
    if (baseline == null || basis == 'raw') return 'raw ${_formatFeatureValue(key, raw)}';
    return 'raw ${_formatFeatureValue(key, raw)} · peer ${_formatFeatureValue(key, baseline)}';
  }

  String _formatFeatureValue(String key, double? value, {bool compared = false}) {
    if (value == null || !value.isFinite) return '—';
    const percentages = {
      'revenue_growth', 'earnings_growth', 'quarter_growth', 'roe', 'roa',
      'net_margin', 'total_return', 'relative_return', 'near_52w_high',
      'yield_ttm', 'yield_5y', 'payout',
    };
    if (percentages.contains(key)) return '${(value * 100).toStringAsFixed(2)}%';
    if (key == 'price_intrinsic' && !compared) return value.toStringAsFixed(0);
    return '${value.toStringAsFixed(2)}x';
  }

  Widget _panel(Widget child) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: _surface,
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: _border),
    ),
    child: child,
  );

  Widget _badge(String text, Color color) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
    decoration: BoxDecoration(
      color: color.withAlpha(12),
      borderRadius: BorderRadius.circular(999),
      border: Border.all(color: color),
    ),
    child: Text(text, style: TextStyle(color: color, fontSize: 10, letterSpacing: .8, fontWeight: FontWeight.w800)),
  );

  Color _segmentColor(String segment) {
    switch (segment.toLowerCase()) {
      case 'growth':
        return _amber;
      case 'financial':
        return _green;
      case 'performance':
        return const Color(0xFFB98BFF);
      case 'dividend':
        return const Color(0xFF7DDDB6);
      default:
        return _accent;
    }
  }
}
