import 'package:flutter/material.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';

/// A single conversation thread with one partner, rendered as chat bubbles
/// with a compose bar at the bottom - built on top of the existing
/// sender->recipient InAppMessage model (there's no separate "conversation"
/// concept server-side, so this screen is what turns that flat message log
/// into something that reads like a normal chat).
class ChatThreadScreen extends StatefulWidget {
  final String partnerEmail;
  final String partnerName;
  final List<Map<String, dynamic>> initialMessages;

  const ChatThreadScreen({
    super.key,
    required this.partnerEmail,
    required this.partnerName,
    required this.initialMessages,
  });

  @override
  State<ChatThreadScreen> createState() => _ChatThreadScreenState();
}

class _ChatThreadScreenState extends State<ChatThreadScreen> {
  late final List<Map<String, dynamic>> _messages = List.of(widget.initialMessages);
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    _sortMessages();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToBottom();
      _markIncomingRead();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _sortMessages() {
    _messages.sort((a, b) {
      final aDate = DateTime.tryParse((a['created_at'] ?? '').toString()) ?? DateTime.now();
      final bDate = DateTime.tryParse((b['created_at'] ?? '').toString()) ?? DateTime.now();
      return aDate.compareTo(bDate);
    });
  }

  void _scrollToBottom() {
    if (!_scrollController.hasClients) return;
    _scrollController.animateTo(
      _scrollController.position.maxScrollExtent,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
    );
  }

  Future<void> _markIncomingRead() async {
    for (final m in _messages) {
      if (m['direction'] != 'outgoing' && m['is_read'] != true && m['id'] != null) {
        try {
          await markMessageRead(m['id'].toString());
        } catch (_) {
          // Best-effort - a failed read receipt shouldn't block viewing the thread.
        }
      }
    }
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _sending) return;
    setState(() => _sending = true);
    final optimistic = {
      'body': text,
      'direction': 'outgoing',
      'created_at': DateTime.now().toIso8601String(),
      'from_name': 'Me',
      'to_email': widget.partnerEmail,
      'to_name': widget.partnerName,
      'is_read': false,
    };
    setState(() {
      _messages.add(optimistic);
      _controller.clear();
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    try {
      await sendMessage({'recipient_email': widget.partnerEmail, 'body': text});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not send: $e'), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  String _formatTime(dynamic raw) {
    final dt = DateTime.tryParse((raw ?? '').toString());
    if (dt == null) return '';
    final local = dt.toLocal();
    final hour = local.hour % 12 == 0 ? 12 : local.hour % 12;
    final minute = local.minute.toString().padLeft(2, '0');
    final period = local.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: Text(widget.partnerName, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: _messages.isEmpty
                  ? Center(
                      child: Text('Say hello to ${widget.partnerName}.',
                          style: TextStyle(color: AppColors.muted)),
                    )
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                      itemCount: _messages.length,
                      itemBuilder: (context, index) {
                        final m = _messages[index];
                        final outgoing = m['direction'] == 'outgoing';
                        return _MessageBubble(
                          body: (m['body'] ?? '').toString(),
                          outgoing: outgoing,
                          time: _formatTime(m['created_at']),
                        );
                      },
                    ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        minLines: 1,
                        maxLines: 4,
                        style: const TextStyle(color: AppColors.textDark),
                        decoration: InputDecoration(
                          hintText: 'Message ${widget.partnerName}',
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(24)),
                        ),
                        onSubmitted: (_) => _send(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      decoration: const BoxDecoration(color: AppColors.primary, shape: BoxShape.circle),
                      child: IconButton(
                        onPressed: _sending ? null : _send,
                        icon: _sending
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.send, color: Colors.white, size: 20),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final String body;
  final bool outgoing;
  final String time;
  const _MessageBubble({required this.body, required this.outgoing, required this.time});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: outgoing ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: outgoing ? AppColors.primary : AppColors.card,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(outgoing ? 16 : 4),
            bottomRight: Radius.circular(outgoing ? 4 : 16),
          ),
          boxShadow: const [BoxShadow(color: Color(0x0C000000), blurRadius: 8, offset: Offset(0, 2))],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(body, style: TextStyle(color: outgoing ? Colors.white : AppColors.textDark)),
            if (time.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(time,
                  style: TextStyle(
                      color: outgoing ? Colors.white.withValues(alpha: 0.75) : AppColors.muted, fontSize: 10)),
            ],
          ],
        ),
      ),
    );
  }
}
