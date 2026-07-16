import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/client.dart';
import '../api/endpoints.dart';
import '../auth/auth_provider.dart';
import '../storage/offline_cache.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/app_screen.dart';
import '../widgets/primary_button.dart';

const _naira = '₦';

const _tags = [
  {'label': 'Operations', 'color': 0xFF14B8A6},
  {'label': 'Utilities', 'color': 0xFFF59E0B},
  {'label': 'Supplies', 'color': 0xFF6366F1},
  {'label': 'Payroll', 'color': 0xFFEC4899},
  {'label': 'Maintenance', 'color': 0xFF22C55E},
  {'label': 'Transport', 'color': 0xFFEF4444},
];

const _types = ['expense', 'bill', 'receipt'];
const _statuses = ['pending', 'due', 'paid'];

String _money(dynamic v) =>
    '$_naira${double.tryParse(v?.toString() ?? '0')?.toStringAsFixed(2) ?? '0.00'}';

class ExpensesScreen extends StatefulWidget {
  const ExpensesScreen({super.key});

  @override
  State<ExpensesScreen> createState() => _ExpensesScreenState();
}

class _ExpensesScreenState extends State<ExpensesScreen> {
  Map<String, dynamic>? _data;
  bool _refreshing = false;
  bool _saving = false;
  String? _msg;
  String? _error;
  String _activeType = 'all';

  final _title = TextEditingController();
  final _vendor = TextEditingController();
  final _amount = TextEditingController();
  final _note = TextEditingController();
  String _type = 'expense';
  String _status = 'pending';
  String _category = 'Operations';
  int _color = 0xFF14B8A6;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() {
      _refreshing = true;
      _error = null;
    });
    final scope = context.read<AuthProvider>().scopeKey;
    try {
      await replayOfflineQueue();
      final snap = await loadExpenses();
      setState(() => _data = snap);
      await writeCache('expenses', snap, scope);
    } catch (e) {
      final cached = await readCache('expenses', scope);
      if (cached?['data'] != null && mounted) {
        setState(() {
          _data = cached!['data'] as Map<String, dynamic>?;
          _error = 'Showing cached data.';
        });
      } else {
        setState(() => _error = e.toString());
      }
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  Future<void> _save() async {
    if (_title.text.trim().isEmpty || _amount.text.trim().isEmpty) {
      setState(() => _error = 'Title and amount are required.');
      return;
    }
    setState(() {
      _saving = true;
      _msg = null;
      _error = null;
    });
    try {
      await createExpense({
        'title': _title.text.trim(),
        'vendor': _vendor.text.trim(),
        'amount': _amount.text.trim(),
        'type': _type,
        'status': _status,
        'category': _category,
        'color': '#${_color.toRadixString(16).padLeft(8, '0').substring(2)}',
        'note': _note.text.trim(),
        'date': DateTime.now().toIso8601String().substring(0, 10),
      });
      _title.clear();
      _vendor.clear();
      _amount.clear();
      _note.clear();
      setState(() => _msg = 'Expense saved.');
      await _load();
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _delete(dynamic id) async {
    try {
      await deleteExpense(id);
      await _load();
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  List<dynamic> get _filtered {
    final records =
        ((_data?['records'] ?? _data?['expenses'] ?? []) as List).cast<dynamic>();
    if (_activeType == 'all') return records;
    return records
        .where((r) => (r as Map)['type'] == _activeType)
        .toList();
  }

  @override
  void dispose() {
    _title.dispose();
    _vendor.dispose();
    _amount.dispose();
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RefreshableScreen(
      onRefresh: _load,
      children: [
        const Text(
          'Expenses',
          style: TextStyle(
              color: AppColors.text,
              fontSize: 28,
              fontWeight: FontWeight.w900),
        ),
        if (_msg != null)
          _Banner(text: _msg!, color: AppColors.success),
        if (_error != null)
          _Banner(text: _error!, color: AppColors.danger),

        // Type filter chips
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              for (final t in ['all', ..._types])
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(t),
                    selected: _activeType == t,
                    onSelected: (_) => setState(() => _activeType = t),
                    selectedColor: AppColors.primarySoft,
                    labelStyle: TextStyle(
                      color: _activeType == t
                          ? AppColors.primary
                          : AppColors.mutedDark,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
            ],
          ),
        ),

        // Record list
        if (_refreshing && _data == null)
          const Center(child: CircularProgressIndicator(color: AppColors.primary)),
        for (final r in _filtered)
          _ExpenseRow(
            record: r as Map<String, dynamic>,
            onDelete: () => _delete((r as Map)['id']),
          ),

        // Add new expense form
        AppCard(
          children: [
            const Text(
              'Add expense',
              style: TextStyle(
                  color: AppColors.textDark,
                  fontSize: 16,
                  fontWeight: FontWeight.w900),
            ),
            _field(_title, 'Title *'),
            _field(_vendor, 'Vendor / supplier'),
            _field(_amount, 'Amount *', type: TextInputType.number),
            _field(_note, 'Note'),
            _DropdownRow(
              label: 'Type',
              value: _type,
              items: _types,
              onChanged: (v) => setState(() => _type = v!),
            ),
            _DropdownRow(
              label: 'Status',
              value: _status,
              items: _statuses,
              onChanged: (v) => setState(() => _status = v!),
            ),
            // Category picker
            Wrap(
              spacing: 8,
              children: [
                for (final t in _tags)
                  ChoiceChip(
                    label: Text(t['label'] as String),
                    selected: _category == t['label'],
                    selectedColor:
                        Color(t['color'] as int).withValues(alpha: 0.25),
                    onSelected: (_) => setState(() {
                      _category = t['label'] as String;
                      _color = t['color'] as int;
                    }),
                    labelStyle: TextStyle(
                      color: _category == t['label']
                          ? Color(t['color'] as int)
                          : AppColors.mutedDark,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
              ],
            ),
            PrimaryButton(
              title: _saving ? 'Saving...' : 'Save expense',
              onPressed: _save,
              loading: _saving,
            ),
          ],
        ),
      ],
    );
  }

  Widget _field(TextEditingController ctrl, String hint,
      {TextInputType type = TextInputType.text}) {
    return TextField(
      controller: ctrl,
      keyboardType: type,
      style: const TextStyle(color: AppColors.textDark),
      decoration: InputDecoration(hintText: hint),
    );
  }
}

class _DropdownRow extends StatelessWidget {
  final String label;
  final String value;
  final List<String> items;
  final ValueChanged<String?> onChanged;
  const _DropdownRow(
      {required this.label,
      required this.value,
      required this.items,
      required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text('$label: ',
            style: const TextStyle(
                color: AppColors.mutedDark, fontWeight: FontWeight.w700)),
        DropdownButton<String>(
          value: value,
          dropdownColor: AppColors.card,
          style: const TextStyle(color: AppColors.textDark),
          items: items
              .map((i) => DropdownMenuItem(value: i, child: Text(i)))
              .toList(),
          onChanged: onChanged,
        ),
      ],
    );
  }
}

class _ExpenseRow extends StatelessWidget {
  final Map<String, dynamic> record;
  final VoidCallback onDelete;
  const _ExpenseRow({required this.record, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final color = Color(
      int.tryParse(
              (record['color'] as String? ?? '#14b8a6')
                  .replaceFirst('#', '0xFF')) ??
          0xFF14B8A6,
    );
    return AppCard(
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (record['title'] ?? 'Expense').toString(),
                    style: const TextStyle(
                        color: AppColors.textDark,
                        fontWeight: FontWeight.w900),
                  ),
                  Text(
                    _money(record['amount']),
                    style: const TextStyle(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w900),
                  ),
                  if (record['vendor'] != null)
                    Text(record['vendor'].toString(),
                        style:
                            const TextStyle(color: AppColors.mutedDark)),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    (record['category'] ?? record['type'] ?? '').toString(),
                    style: TextStyle(
                        color: color,
                        fontSize: 11,
                        fontWeight: FontWeight.w800),
                  ),
                ),
                const SizedBox(height: 4),
                GestureDetector(
                  onTap: onDelete,
                  child: const Icon(Icons.delete_outline,
                      color: AppColors.danger, size: 20),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }
}

class _Banner extends StatelessWidget {
  final String text;
  final Color color;
  const _Banner({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(text,
          style: TextStyle(color: color, fontWeight: FontWeight.w600)),
    );
  }
}
