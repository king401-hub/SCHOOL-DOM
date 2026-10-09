import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api/client.dart';
import '../api/mail_endpoints.dart';
import 'reply_screen.dart';

class MessageDetailScreen extends StatefulWidget {
  final int id;
  const MessageDetailScreen({super.key, required this.id});

  @override
  State<MessageDetailScreen> createState() => _MessageDetailScreenState();
}

class _MessageDetailScreenState extends State<MessageDetailScreen> {
  Map<String, dynamic>? _message;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await loadMessage(widget.id);
      setState(() => _message = data);
      if (data['is_read'] != true) {
        markRead(widget.id).ignore();
      }
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final message = _message;
    return Scaffold(
      appBar: AppBar(title: const Text('Message')),
      body: message == null
          ? Center(child: Text(_error ?? ''))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  (message['subject'] as String?)?.isNotEmpty == true
                      ? message['subject']
                      : '(no subject)',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text('From: ${message['from_address'] ?? ''}'),
                if ((message['to_address'] as String?)?.isNotEmpty == true)
                  Text('To: ${message['to_address']}'),
                if ((message['received_at'] as String?)?.isNotEmpty == true)
                  Text('Received: ${message['received_at']}'),
                const Divider(height: 32),
                SelectableText(
                  (message['body_text'] as String?)?.isNotEmpty == true
                      ? message['body_text']
                      : (message['body_html'] as String?) ?? '(no content)',
                ),
                if ((message['attachments'] as List?)?.isNotEmpty == true) ...[
                  const Divider(height: 32),
                  const Text('Attachments', style: TextStyle(fontWeight: FontWeight.bold)),
                  for (final attachment in message['attachments'] as List)
                    ListTile(
                      leading: const Icon(Icons.attach_file),
                      title: Text(attachment['filename'] as String? ?? ''),
                      onTap: () {
                        final url = attachment['file'] as String?;
                        if (url != null) launchUrl(Uri.parse(url));
                      },
                    ),
                ],
              ],
            ),
      floatingActionButton: message == null
          ? null
          : FloatingActionButton.extended(
              icon: const Icon(Icons.reply),
              label: const Text('Reply'),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => ReplyScreen(message: message)),
              ),
            ),
    );
  }
}
