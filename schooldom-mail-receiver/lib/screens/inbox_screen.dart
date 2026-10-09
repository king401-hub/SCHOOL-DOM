import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/client.dart';
import '../api/mail_endpoints.dart';
import '../auth/auth_provider.dart';
import 'message_detail_screen.dart';

class InboxScreen extends StatefulWidget {
  const InboxScreen({super.key});

  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen> {
  List<dynamic> _messages = [];
  bool _loading = true;
  String? _error;
  String? _accountFilter;

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
      final data = await loadMessages(account: _accountFilter);
      setState(() => _messages = (data['results'] as List?) ?? const []);
    } on ApiException catch (e) {
      setState(() => _error = e.statusCode == 403
          ? 'You do not have access to the support mail inbox.'
          : e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final accounts = _messages
        .map((m) => m['account_label'] as String)
        .toSet()
        .toList()
      ..sort();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Support Mail'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthProvider>().signOut(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _buildBody(accounts),
      ),
    );
  }

  Widget _buildBody(List<String> accounts) {
    if (_loading && _messages.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return ListView(
        children: [
          Padding(
            padding: const EdgeInsets.all(24),
            child: Text(_error!, textAlign: TextAlign.center),
          ),
        ],
      );
    }
    if (_messages.isEmpty) {
      return ListView(
        children: const [
          Padding(
            padding: EdgeInsets.all(24),
            child: Text('No mail yet.', textAlign: TextAlign.center),
          ),
        ],
      );
    }

    return Column(
      children: [
        if (accounts.length > 1)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Wrap(
              spacing: 8,
              children: [
                ChoiceChip(
                  label: const Text('All'),
                  selected: _accountFilter == null,
                  onSelected: (_) {
                    setState(() => _accountFilter = null);
                    _load();
                  },
                ),
                for (final account in accounts)
                  ChoiceChip(
                    label: Text(account),
                    selected: _accountFilter == account,
                    onSelected: (_) {
                      setState(() => _accountFilter = account);
                      _load();
                    },
                  ),
              ],
            ),
          ),
        Expanded(
          child: ListView.separated(
            itemCount: _messages.length,
            separatorBuilder: (_, _) => const Divider(height: 1),
            itemBuilder: (context, index) {
              final message = _messages[index] as Map<String, dynamic>;
              final isRead = message['is_read'] == true;
              return ListTile(
                title: Text(
                  (message['subject'] as String?)?.isNotEmpty == true
                      ? message['subject']
                      : '(no subject)',
                  style: TextStyle(fontWeight: isRead ? FontWeight.normal : FontWeight.bold),
                ),
                subtitle: Text(message['from_address'] as String? ?? ''),
                trailing: message['has_attachments'] == true
                    ? const Icon(Icons.attach_file, size: 18)
                    : null,
                onTap: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => MessageDetailScreen(id: message['id'] as int),
                    ),
                  );
                  _load();
                },
              );
            },
          ),
        ),
      ],
    );
  }
}
