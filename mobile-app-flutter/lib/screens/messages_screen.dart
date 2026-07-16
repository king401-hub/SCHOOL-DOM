import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api/endpoints.dart';
import '../api/config.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/app_screen.dart';

class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key});

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  List<dynamic> _messages = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await loadMessages();
      setState(() => _messages =
          (data['messages'] ?? data['inbox'] ?? []) as List<dynamic>);
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshableScreen(
      onRefresh: _load,
      children: [
        const Text(
          'Messages',
          style: TextStyle(
              color: AppColors.text,
              fontSize: 28,
              fontWeight: FontWeight.w900),
        ),
        if (_error != null)
          Text(_error!, style: const TextStyle(color: AppColors.danger)),
        if (_messages.isEmpty && _error == null)
          const Text('No messages yet.',
              style: TextStyle(color: AppColors.muted)),
        for (final msg in _messages) _MessageCard(msg: msg as Map<String, dynamic>),
      ],
    );
  }
}

class _MessageCard extends StatelessWidget {
  final Map<String, dynamic> msg;
  const _MessageCard({required this.msg});

  String _resolveUrl(Map<String, dynamic> att) {
    final url =
        (att['url'] ?? att['preview_url'] ?? att['previewUrl'] ?? '') as String;
    if (url.isEmpty || url.startsWith('http')) return url;
    return '$apiBaseUrl${url.startsWith('/') ? '' : '/'}$url';
  }

  bool _isImage(Map<String, dynamic> att) {
    final ct =
        (att['content_type'] ?? att['contentType'] ?? att['type'] ?? '')
            .toString()
            .toLowerCase();
    final name = (att['name'] ?? att['filename'] ?? '').toString().toLowerCase();
    final url = _resolveUrl(att).toLowerCase().split('?').first;
    return ct.startsWith('image/') ||
        RegExp(r'\.(png|jpe?g|gif|webp|bmp|svg)$').hasMatch(name) ||
        RegExp(r'\.(png|jpe?g|gif|webp|bmp|svg)$').hasMatch(url);
  }

  @override
  Widget build(BuildContext context) {
    final attachments =
        ((msg['attachments'] ?? []) as List).cast<Map<String, dynamic>>();
    return AppCard(
      children: [
        Text(
          (msg['subject'] ?? msg['title'] ?? 'Message').toString(),
          style: const TextStyle(
              color: AppColors.textDark, fontWeight: FontWeight.w900),
        ),
        if ((msg['body'] ?? msg['message'] ?? '').toString().isNotEmpty)
          Text(
            (msg['body'] ?? msg['message']).toString(),
            style: const TextStyle(color: AppColors.mutedDark),
          ),
        for (final att in attachments) ...[
          const SizedBox(height: 4),
          GestureDetector(
            onTap: () {
              final url = _resolveUrl(att);
              if (url.isNotEmpty) launchUrl(Uri.parse(url));
            },
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_isImage(att) && _resolveUrl(att).isNotEmpty)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: Image.network(
                      _resolveUrl(att),
                      height: 180,
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) => const SizedBox.shrink(),
                    ),
                  ),
                Text(
                  (att['name'] ?? att['filename'] ?? att['url'] ?? 'Attachment')
                      .toString(),
                  style: const TextStyle(
                      color: AppColors.primary, fontWeight: FontWeight.w800),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
