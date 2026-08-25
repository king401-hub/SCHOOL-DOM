import 'dart:async';
import 'package:flutter/material.dart';
import '../api/admin_endpoints.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';

enum _FinanceTab { overview, transactions, live }

class FinanceScreen extends StatefulWidget {
  const FinanceScreen({super.key});

  @override
  State<FinanceScreen> createState() => _FinanceScreenState();
}

class _FinanceScreenState extends State<FinanceScreen> {
  _FinanceTab _tab = _FinanceTab.overview;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'Finance',
                      style: TextStyle(
                          color: AppColors.text,
                          fontSize: 28,
                          fontWeight: FontWeight.w900),
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: _SegmentedToggle(tab: _tab, onChanged: (v) => setState(() => _tab = v)),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: switch (_tab) {
                _FinanceTab.overview => const _OverviewView(),
                _FinanceTab.transactions => const _HistoryView(),
                _FinanceTab.live => const _LiveTransactionsView(),
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _SegmentedToggle extends StatelessWidget {
  final _FinanceTab tab;
  final ValueChanged<_FinanceTab> onChanged;
  const _SegmentedToggle({required this.tab, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.surfaceSoft,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Expanded(
            child: _SegmentButton(
              label: 'Overview',
              selected: tab == _FinanceTab.overview,
              onTap: () => onChanged(_FinanceTab.overview),
            ),
          ),
          Expanded(
            child: _SegmentButton(
              label: 'Transactions',
              selected: tab == _FinanceTab.transactions,
              onTap: () => onChanged(_FinanceTab.transactions),
            ),
          ),
          Expanded(
            child: _SegmentButton(
              label: 'Live',
              selected: tab == _FinanceTab.live,
              onTap: () => onChanged(_FinanceTab.live),
            ),
          ),
        ],
      ),
    );
  }
}

class _SegmentButton extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _SegmentButton(
      {required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          gradient: selected ? AppGradients.brand : null,
          borderRadius: BorderRadius.circular(9),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : AppColors.muted,
            fontWeight: FontWeight.w800,
            fontSize: 13,
          ),
        ),
      ),
    );
  }
}

class _OverviewView extends StatefulWidget {
  const _OverviewView();

  @override
  State<_OverviewView> createState() => _OverviewViewState();
}

class _OverviewViewState extends State<_OverviewView> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await loadFinanceOverview();
      setState(() => _data = data);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _naira(dynamic value) {
    final amount = double.tryParse(value?.toString() ?? '') ?? 0;
    final whole = amount.truncate().toString();
    final withCommas = whole.replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
    return '₦$withCommas';
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _data == null) return const SkeletonList();
    if (_error != null && _data == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, color: AppColors.danger, size: 40),
              const SizedBox(height: 12),
              const Text("Couldn't load the finance summary.",
                  style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
              const SizedBox(height: 16),
              SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: _load)),
            ],
          ),
        ),
      );
    }
    final expected = double.tryParse(_data?['expected_fee_amount']?.toString() ?? '') ?? 0;
    final collected = double.tryParse(_data?['amount_received']?.toString() ?? '') ?? 0;
    final outstanding = double.tryParse(_data?['outstanding_balance']?.toString() ?? '') ?? 0;
    final rate = expected > 0 ? (collected / expected * 100).clamp(0, 100) : 0.0;

    return BrandedRefresh(
      onRefresh: _load,
      showSpinner: _loading,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(gradient: AppGradients.brand, borderRadius: BorderRadius.circular(18)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Total Collected',
                    style: TextStyle(color: Colors.white70, fontWeight: FontWeight.w700, fontSize: 12)),
                const SizedBox(height: 4),
                Text(_naira(collected),
                    style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.w900)),
                const SizedBox(height: 4),
                Text('${rate.toStringAsFixed(0)}% collection rate',
                    style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.w700, fontSize: 12)),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _SummaryTile(
                    label: 'Outstanding', value: _naira(outstanding), color: AppColors.warning),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _SummaryTile(label: 'Expected Fees', value: _naira(expected), color: AppColors.primary),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _SummaryTile(
                    label: 'Pending', value: '${_data?['pending_fees'] ?? 0}', color: AppColors.muted),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _SummaryTile(
                    label: 'Overdue', value: '${_data?['overdue_fees'] ?? 0}', color: AppColors.danger),
              ),
            ],
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }
}

class _SummaryTile extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _SummaryTile({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      elevated: true,
      children: [
        Text(label, style: const TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 12)),
        Text(value, style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.w900)),
      ],
    );
  }
}

class _HistoryView extends StatefulWidget {
  const _HistoryView();

  @override
  State<_HistoryView> createState() => _HistoryViewState();
}

class _HistoryViewState extends State<_HistoryView> {
  List<dynamic> _items = [];
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await loadFinanceTransactions(limit: 100);
      setState(() {
        _items = (data['transactions'] ?? []) as List<dynamic>;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return BrandedRefresh(
      onRefresh: _load,
      showSpinner: _loading && _items.isNotEmpty,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
        children: [
          if (_error != null)
            Text(_error!, style: const TextStyle(color: AppColors.danger)),
          if (!_loading && _items.isEmpty && _error == null)
            Padding(
              padding: const EdgeInsets.only(top: 40),
              child: Center(
                child: Text('No transactions yet.',
                    style: TextStyle(color: AppColors.muted)),
              ),
            ),
          for (final tx in _items) ...[
            _TransactionCard(tx: tx as Map<String, dynamic>),
            const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }
}

class _LiveTransactionsView extends StatefulWidget {
  const _LiveTransactionsView();

  @override
  State<_LiveTransactionsView> createState() => _LiveTransactionsViewState();
}

class _LiveTransactionsViewState extends State<_LiveTransactionsView> {
  List<dynamic> _items = [];
  String? _error;
  bool _loading = true;
  bool _refreshing = false;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 8), (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final data = await loadFinanceTransactions(limit: 30);
      if (!mounted) return;
      setState(() {
        _items = (data['transactions'] ?? []) as List<dynamic>;
        _error = null;
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  /// Wraps [_load] with a visible branded spinner for an explicit
  /// pull-to-refresh - the 8-second auto-poll keeps calling [_load] directly
  /// and stays silent, so this "live" screen doesn't flash a spinner on its
  /// own timer.
  Future<void> _pullRefresh() async {
    setState(() => _refreshing = true);
    await _load();
    if (mounted) setState(() => _refreshing = false);
  }

  @override
  Widget build(BuildContext context) {
    return BrandedRefresh(
      onRefresh: _pullRefresh,
      showSpinner: _refreshing,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
        children: [
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                margin: const EdgeInsets.only(right: 8),
                decoration: const BoxDecoration(
                  color: AppColors.success,
                  shape: BoxShape.circle,
                ),
              ),
              Text(
                'Live — refreshing every few seconds',
                style: TextStyle(
                    color: AppColors.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_error != null)
            Text(_error!, style: const TextStyle(color: AppColors.danger)),
          if (!_loading && _items.isEmpty && _error == null)
            Padding(
              padding: const EdgeInsets.only(top: 40),
              child: Center(
                child: Text('No live activity yet.',
                    style: TextStyle(color: AppColors.muted)),
              ),
            ),
          for (final tx in _items) ...[
            _TransactionCard(tx: tx as Map<String, dynamic>),
            const SizedBox(height: 12),
          ],
        ],
      ),
    );
  }
}

class _TransactionCard extends StatelessWidget {
  final Map<String, dynamic> tx;
  const _TransactionCard({required this.tx});

  Color _statusColor(String status) {
    switch (status) {
      case 'successful':
        return AppColors.success;
      case 'failed':
        return AppColors.danger;
      default:
        return AppColors.warning;
    }
  }

  String _typeLabel(String type) =>
      type.split('_').map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}').join(' ');

  @override
  Widget build(BuildContext context) {
    final status = (tx['status'] ?? '').toString();
    final currency = (tx['currency'] ?? 'NGN').toString();
    final amount = tx['amount'];
    return AppCard(
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                _typeLabel((tx['tx_type'] ?? '').toString()),
                style: const TextStyle(
                    color: AppColors.textDark, fontWeight: FontWeight.w900),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: _statusColor(status).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                status.isEmpty ? 'pending' : status,
                style: TextStyle(
                  color: _statusColor(status),
                  fontWeight: FontWeight.w800,
                  fontSize: 11,
                ),
              ),
            ),
          ],
        ),
        Text(
          '$currency $amount',
          style: const TextStyle(
              color: AppColors.textDark,
              fontSize: 20,
              fontWeight: FontWeight.w900),
        ),
        if ((tx['narration'] ?? '').toString().isNotEmpty)
          Text(
            tx['narration'].toString(),
            style: const TextStyle(color: AppColors.mutedDark),
          ),
        Text(
          (tx['reference'] ?? '').toString(),
          style: TextStyle(color: AppColors.muted, fontSize: 11),
        ),
      ],
    );
  }
}
