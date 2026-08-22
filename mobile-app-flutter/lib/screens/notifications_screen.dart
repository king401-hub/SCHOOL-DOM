import 'package:flutter/material.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
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
      final data = await loadNotifications();
      setState(() {
        _items = (data['notifications'] ?? []) as List<dynamic>;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _markRead(Map<String, dynamic> item) async {
    if (item['is_read'] == true) return;
    setState(() => item['is_read'] = true);
    try {
      await markNotificationRead(item['id'].toString());
    } catch (_) {
      if (mounted) setState(() => item['is_read'] = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text(
          'Notifications',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          color: AppColors.primary,
          child: ListView(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            children: [
              if (_error != null)
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
              if (!_loading && _items.isEmpty && _error == null)
                Padding(
                  padding: const EdgeInsets.only(top: 40),
                  child: Center(
                    child: Text('No notifications yet.',
                        style: TextStyle(color: AppColors.muted)),
                  ),
                ),
              for (final raw in _items) ...[
                _NotificationCard(
                  item: raw as Map<String, dynamic>,
                  onTap: () => _markRead(raw),
                ),
                const SizedBox(height: 12),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final VoidCallback onTap;
  const _NotificationCard({required this.item, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final isRead = item['is_read'] == true;
    return GestureDetector(
      onTap: onTap,
      child: AppCard(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (!isRead)
                Container(
                  margin: const EdgeInsets.only(top: 6, right: 8),
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AppColors.primary,
                    shape: BoxShape.circle,
                  ),
                ),
              Expanded(
                child: Text(
                  (item['title'] ?? 'Notification').toString(),
                  style: TextStyle(
                    color: AppColors.textDark,
                    fontWeight: isRead ? FontWeight.w700 : FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          if ((item['message'] ?? '').toString().isNotEmpty)
            Text(
              item['message'].toString(),
              style: const TextStyle(color: AppColors.mutedDark),
            ),
        ],
      ),
    );
  }
}
