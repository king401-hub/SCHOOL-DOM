import 'package:flutter/material.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/avatar.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';
import 'chat_thread_screen.dart';

/// Conversation list, one row per contact - built from the server-side
/// aggregated /api/app/messages/conversations/ endpoint so a conversation
/// can never silently disappear just because other people sent messages
/// more recently (that was the bug with grouping the old, tenant-wide
/// 20-message-capped snapshot on the client instead).
class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key});

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> with WidgetsBindingObserver {
  List<_Conversation> _conversations = [];
  List<dynamic> _recipients = [];
  String? _error;
  bool _loading = true;
  bool _initialLoadDone = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      // Conversations come from the aggregated endpoint (no message cap);
      // recipients (for "start a new conversation") still come from the
      // lighter snapshot endpoint, which already computes that list cheaply.
      final results = await Future.wait([loadConversations(), loadMessages()]);
      final conversations = (results[0]['conversations'] ?? []) as List<dynamic>;
      setState(() {
        _conversations = conversations
            .cast<Map<String, dynamic>>()
            .map(_Conversation.fromJson)
            .toList();
        _recipients = (results[1]['recipients'] ?? []) as List<dynamic>;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _initialLoadDone = true;
        });
      }
    }
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
    List<Map<String, dynamic>> initialMessages = const [];
    try {
      final data = await loadMessageThread(conversation.partnerEmail);
      initialMessages = ((data['messages'] ?? []) as List<dynamic>).cast<Map<String, dynamic>>();
    } catch (_) {
      // Falls through with an empty thread - ChatThreadScreen still lets you
      // send a new message even if history failed to load just now.
    }
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChatThreadScreen(
          partnerEmail: conversation.partnerEmail,
          partnerName: conversation.partnerName,
          partnerProfilePicture: conversation.partnerProfilePicture,
          initialMessages: initialMessages,
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
          partnerProfilePicture: (picked['profile_picture'] as String?),
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
        child: !_initialLoadDone && _loading
            ? const SkeletonList()
            : _error != null && _conversations.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline, color: AppColors.danger, size: 40),
                          const SizedBox(height: 12),
                          const Text("Couldn't load your messages.",
                              style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                          const SizedBox(height: 4),
                          Text('Check your connection and try again.',
                              textAlign: TextAlign.center, style: TextStyle(color: AppColors.muted, fontSize: 13)),
                          const SizedBox(height: 16),
                          SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: _load)),
                        ],
                      ),
                    ),
                  )
                : BrandedRefresh(
                    onRefresh: _load,
                    showSpinner: _loading,
                    child: ListView(
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                      children: [
                        if (_conversations.isEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 40),
                            child: Center(
                              child: Text('No conversations yet. Tap + to message someone.',
                                  textAlign: TextAlign.center, style: TextStyle(color: AppColors.muted)),
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
  final String? partnerProfilePicture;
  final String lastBody;
  final bool lastHasAttachment;
  final String lastAttachmentType;
  final DateTime? lastAt;
  final int unreadCount;
  const _Conversation({
    required this.partnerEmail,
    required this.partnerName,
    required this.partnerProfilePicture,
    required this.lastBody,
    required this.lastHasAttachment,
    required this.lastAttachmentType,
    required this.lastAt,
    required this.unreadCount,
  });

  factory _Conversation.fromJson(Map<String, dynamic> json) => _Conversation(
        partnerEmail: (json['partner_email'] ?? '').toString(),
        partnerName: (json['partner_name'] ?? 'Unknown').toString(),
        partnerProfilePicture: (json['partner_profile_picture'] as String?),
        lastBody: (json['last_body'] ?? '').toString(),
        lastHasAttachment: json['last_has_attachment'] == true,
        lastAttachmentType: (json['last_attachment_type'] ?? '').toString(),
        lastAt: DateTime.tryParse((json['last_at'] ?? '').toString()),
        unreadCount: (json['unread_count'] as num?)?.toInt() ?? 0,
      );

  String get preview {
    if (lastBody.isNotEmpty) return lastBody;
    if (!lastHasAttachment) return '';
    if (lastAttachmentType.startsWith('image/')) return '📷 Photo';
    if (lastAttachmentType.startsWith('video/')) return '🎥 Video';
    if (lastAttachmentType.startsWith('audio/')) return '🎤 Voice note';
    return '📎 Attachment';
  }
}

class _ConversationTile extends StatelessWidget {
  final _Conversation conversation;
  final String Function(DateTime?) formatTime;
  final VoidCallback onTap;
  const _ConversationTile({required this.conversation, required this.formatTime, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AppCard(
        children: [
          Row(
            children: [
              Avatar(name: conversation.partnerName, pictureUrl: conversation.partnerProfilePicture),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(conversation.partnerName,
                        style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                    if (conversation.preview.isNotEmpty)
                      Text(conversation.preview,
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
                        leading: Avatar(
                          name: (r['name'] ?? 'Contact').toString(),
                          pictureUrl: r['profile_picture'] as String?,
                          size: 36,
                        ),
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
