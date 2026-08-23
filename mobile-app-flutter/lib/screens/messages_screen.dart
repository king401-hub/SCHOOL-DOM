import 'package:flutter/material.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import 'chat_thread_screen.dart';

/// Groups the flat inbox (each message is sender->recipient) into one row
/// per conversation partner, like a normal chat app's conversation list,
/// instead of a flat timeline of individual messages.
class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key});

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  List<dynamic> _messages = [];
  List<dynamic> _recipients = [];
  String? _error;
  bool _loading = true;

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
      final data = await loadMessages();
      setState(() {
        _messages = (data['inbox'] ?? data['messages'] ?? []) as List<dynamic>;
        _recipients = (data['recipients'] ?? []) as List<dynamic>;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _previewText(Map<String, dynamic> m) {
    final body = (m['body'] ?? '').toString();
    if (body.isNotEmpty) return body;
    final attachments = (m['attachments'] ?? []) as List<dynamic>;
    if (attachments.isEmpty) return '';
    final type = (attachments.first as Map<String, dynamic>)['content_type']?.toString() ?? '';
    if (type.startsWith('image/')) return '📷 Photo';
    if (type.startsWith('video/')) return '🎥 Video';
    if (type.startsWith('audio/')) return '🎤 Voice note';
    return '📎 Attachment';
  }

  List<_Conversation> get _conversations {
    final byPartner = <String, _Conversation>{};
    for (final raw in _messages) {
      final m = raw as Map<String, dynamic>;
      final outgoing = m['direction'] == 'outgoing';
      final partnerEmail = (outgoing ? m['to_email'] : m['from_email'])?.toString() ?? '';
      final partnerName = (outgoing ? m['to_name'] : m['from_name'])?.toString() ?? 'Unknown';
      if (partnerEmail.isEmpty) continue;
      final existing = byPartner[partnerEmail];
      final createdAt = DateTime.tryParse((m['created_at'] ?? '').toString());
      final unread = !outgoing && m['is_read'] != true;
      if (existing == null) {
        byPartner[partnerEmail] = _Conversation(
          partnerEmail: partnerEmail,
          partnerName: partnerName,
          lastBody: _previewText(m),
          lastAt: createdAt,
          unreadCount: unread ? 1 : 0,
        );
      } else {
        final isNewer = createdAt != null && (existing.lastAt == null || createdAt.isAfter(existing.lastAt!));
        byPartner[partnerEmail] = _Conversation(
          partnerEmail: partnerEmail,
          partnerName: partnerName,
          lastBody: isNewer ? _previewText(m) : existing.lastBody,
          lastAt: isNewer ? createdAt : existing.lastAt,
          unreadCount: existing.unreadCount + (unread ? 1 : 0),
        );
      }
    }
    final list = byPartner.values.toList();
    list.sort((a, b) {
      if (a.lastAt == null) return 1;
      if (b.lastAt == null) return -1;
      return b.lastAt!.compareTo(a.lastAt!);
    });
    return list;
  }

  String _formatTime(DateTime? dt) {
    if (dt == null) return '';
    final local = dt.toLocal();
    final hour = local.hour % 12 == 0 ? 12 : local.hour % 12;
    final minute = local.minute.toString().padLeft(2, '0');
    final period = local.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  Future<void> _openThread(_Conversation conversation) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChatThreadScreen(
          partnerEmail: conversation.partnerEmail,
          partnerName: conversation.partnerName,
          initialMessages: _messages
              .cast<Map<String, dynamic>>()
              .where((m) => m['from_email'] == conversation.partnerEmail || m['to_email'] == conversation.partnerEmail)
              .toList(),
        ),
      ),
    );
    _load();
  }

  Future<void> _startNewConversation() async {
    final picked = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => _RecipientPicker(recipients: _recipients.cast<Map<String, dynamic>>()),
    );
    if (picked == null || !mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChatThreadScreen(
          partnerEmail: (picked['email'] ?? '').toString(),
          partnerName: (picked['name'] ?? 'Contact').toString(),
          initialMessages: const [],
        ),
      ),
    );
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Messages', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: AppColors.primary,
        onPressed: _startNewConversation,
        child: const Icon(Icons.add_comment_outlined, color: Colors.white),
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
              if (_loading && _messages.isEmpty)
                const Padding(
                  padding: EdgeInsets.only(top: 40),
                  child: Center(child: CircularProgressIndicator(color: AppColors.primary)),
                ),
              if (!_loading && _conversations.isEmpty && _error == null)
                Padding(
                  padding: const EdgeInsets.only(top: 40),
                  child: Center(
                    child: Text('No conversations yet. Tap + to message someone.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: AppColors.muted)),
                  ),
                ),
              for (final conversation in _conversations) ...[
                _ConversationTile(
                  conversation: conversation,
                  formatTime: _formatTime,
                  onTap: () => _openThread(conversation),
                ),
                const SizedBox(height: 10),
              ],
              const SizedBox(height: 64),
            ],
          ),
        ),
      ),
    );
  }
}

class _Conversation {
  final String partnerEmail;
  final String partnerName;
  final String lastBody;
  final DateTime? lastAt;
  final int unreadCount;
  const _Conversation({
    required this.partnerEmail,
    required this.partnerName,
    required this.lastBody,
    required this.lastAt,
    required this.unreadCount,
  });
}

class _ConversationTile extends StatelessWidget {
  final _Conversation conversation;
  final String Function(DateTime?) formatTime;
  final VoidCallback onTap;
  const _ConversationTile({required this.conversation, required this.formatTime, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final initials = conversation.partnerName.trim().isEmpty
        ? '?'
        : conversation.partnerName.trim().split(RegExp(r'\s+')).take(2).map((s) => s[0]).join().toUpperCase();
    return GestureDetector(
      onTap: onTap,
      child: AppCard(
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: const BoxDecoration(color: AppColors.primarySoft, shape: BoxShape.circle),
                alignment: Alignment.center,
                child: Text(initials,
                    style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w900)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(conversation.partnerName,
                        style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                    if (conversation.lastBody.isNotEmpty)
                      Text(conversation.lastBody,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(formatTime(conversation.lastAt),
                      style: TextStyle(color: AppColors.muted, fontSize: 11)),
                  if (conversation.unreadCount > 0) ...[
                    const SizedBox(height: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(color: AppColors.primary, borderRadius: BorderRadius.circular(20)),
                      child: Text(conversation.unreadCount.toString(),
                          style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w800)),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RecipientPicker extends StatelessWidget {
  final List<Map<String, dynamic>> recipients;
  const _RecipientPicker({required this.recipients});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.7),
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
      decoration: const BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('New message',
              style: TextStyle(color: AppColors.textDark, fontSize: 18, fontWeight: FontWeight.w900)),
          const SizedBox(height: 12),
          Flexible(
            child: recipients.isEmpty
                ? const Padding(
                    padding: EdgeInsets.symmetric(vertical: 20),
                    child: Text('No contacts available to message.', style: TextStyle(color: AppColors.mutedDark)),
                  )
                : ListView.builder(
                    shrinkWrap: true,
                    itemCount: recipients.length,
                    itemBuilder: (context, index) {
                      final r = recipients[index];
                      return ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text((r['name'] ?? 'Contact').toString(),
                            style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w700)),
                        subtitle: Text((r['role'] ?? '').toString(),
                            style: const TextStyle(color: AppColors.mutedDark, fontSize: 12)),
                        onTap: () => Navigator.of(context).pop(r),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
