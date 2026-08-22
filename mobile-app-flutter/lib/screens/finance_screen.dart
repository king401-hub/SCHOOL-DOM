import 'dart:async';
import 'package:flutter/material.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';

class FinanceScreen extends StatefulWidget {
  const FinanceScreen({super.key});

  @override
  State<FinanceScreen> createState() => _FinanceScreenState();
}

class _FinanceScreenState extends State<FinanceScreen> {
  bool _showLive = false;

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
              child: _SegmentedToggle(
                showLive: _showLive,
                onChanged: (v) => setState(() => _showLive = v),
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: _showLive
                  ? const _LiveTransactionsView()
                  : const _HistoryView(),
            ),
          ],
        ),
      ),
    );
  }
}

class _SegmentedToggle extends StatelessWidget {
  final bool showLive;
  final ValueChanged<bool> onChanged;
  const _SegmentedToggle({required this.showLive, required this.onChanged});

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
              label: 'History',
              selected: !showLive,
              onTap: () => onChanged(false),
            ),
          ),
          Expanded(
            child: _SegmentButton(
              label: 'Live transactions',
              selected: showLive,
              onTap: () => onChanged(true),
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
          color: selected ? AppColors.primary : Colors.transparent,
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
    return RefreshIndicator(
      onRefresh: _load,
      color: AppColors.primary,
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

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _load,
      color: AppColors.primary,
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
