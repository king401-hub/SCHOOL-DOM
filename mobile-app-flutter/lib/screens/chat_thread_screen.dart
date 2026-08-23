import 'dart:async';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:video_player/video_player.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';

/// A single conversation thread with one partner, rendered as chat bubbles
/// with a compose bar at the bottom - built on top of the existing
/// sender->recipient InAppMessage model (there's no separate "conversation"
/// concept server-side, so this screen is what turns that flat message log
/// into something that reads like a normal chat). Supports photo/video/
/// voice-note attachments and shows sent/read ticks on outgoing messages.
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

class _ChatThreadScreenState extends State<ChatThreadScreen> with WidgetsBindingObserver {
  late final List<Map<String, dynamic>> _messages = List.of(widget.initialMessages);
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _recorder = AudioRecorder();
  bool _sending = false;
  bool _hasText = false;
  bool _isRecording = false;
  Duration _recordDuration = Duration.zero;
  Timer? _recordTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _sortMessages();
    _controller.addListener(() {
      final hasText = _controller.text.trim().isNotEmpty;
      if (hasText != _hasText) setState(() => _hasText = hasText);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToBottom();
      _markIncomingRead();
    });
  }

  // The bug this fixes: leaving the app mid-conversation (e.g. to reply from
  // the web instead) and coming back used to show a stale thread until a
  // manual pull-to-refresh - a new reply from the other side just wasn't
  // there yet. Resuming from the background now refreshes automatically.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refresh();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller.dispose();
    _scrollController.dispose();
    _recordTimer?.cancel();
    _recorder.dispose();
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

  /// Re-fetches the shared snapshot to pick up read receipts on messages this
  /// screen already sent (there's no push/socket layer, so this is manual),
  /// while keeping any optimistic entries that haven't round-tripped yet
  /// (those have no server `id`). Uses the dedicated per-partner thread
  /// endpoint rather than the tenant-wide 20-message-capped snapshot, so a
  /// conversation's history can't silently disappear just because other
  /// people sent messages more recently elsewhere.
  Future<void> _refresh() async {
    try {
      final data = await loadMessageThread(widget.partnerEmail);
      final partnerMessages = ((data['messages'] ?? []) as List<dynamic>).cast<Map<String, dynamic>>();
      final pendingOptimistic = _messages.where((m) => m['id'] == null).toList();
      setState(() {
        _messages
          ..clear()
          ..addAll(partnerMessages)
          ..addAll(pendingOptimistic);
        _sortMessages();
      });
      await _markIncomingRead();
    } catch (_) {
      // Silent - this is just a background refresh of read receipts.
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

  String _guessContentType(String path) {
    final ext = path.split('.').last.toLowerCase();
    const images = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic'};
    const videos = {'mp4', 'mov', 'm4v', '3gp', 'avi'};
    const audios = {'m4a', 'aac', 'mp3', 'wav', 'ogg', 'caf'};
    if (images.contains(ext)) return 'image/$ext';
    if (videos.contains(ext)) return 'video/$ext';
    if (audios.contains(ext)) return 'audio/$ext';
    return 'application/octet-stream';
  }

  Future<void> _sendAttachment(String path, {required String filename}) async {
    if (_sending) return;
    setState(() => _sending = true);
    final optimistic = {
      'body': '',
      'direction': 'outgoing',
      'created_at': DateTime.now().toIso8601String(),
      'is_read': false,
      'attachments': [
        {'name': filename, 'url': path, 'content_type': _guessContentType(path), 'local': true},
      ],
    };
    setState(() => _messages.add(optimistic));
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    try {
      await sendMessageWithAttachment(recipientEmail: widget.partnerEmail, filePath: path, filename: filename);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not send attachment: $e'), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _pickMedia(ImageSource source, {required bool video}) async {
    Navigator.of(context).pop();
    final picker = ImagePicker();
    final file = video
        ? await picker.pickVideo(source: source)
        : await picker.pickImage(source: source, imageQuality: 85);
    if (file == null) return;
    await _sendAttachment(file.path, filename: file.name);
  }

  void _openAttachSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            _AttachOption(
              icon: Icons.photo_camera,
              label: 'Camera',
              color: AppColors.primary,
              onTap: () => _pickMedia(ImageSource.camera, video: false),
            ),
            _AttachOption(
              icon: Icons.image,
              label: 'Gallery',
              color: AppColors.success,
              onTap: () => _pickMedia(ImageSource.gallery, video: false),
            ),
            _AttachOption(
              icon: Icons.videocam,
              label: 'Video',
              color: AppColors.warning,
              onTap: () => _pickMedia(ImageSource.camera, video: true),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _startRecording() async {
    final allowed = await _recorder.hasPermission();
    if (!allowed) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Microphone permission is needed to record a voice note.')),
        );
      }
      return;
    }
    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/voice_${DateTime.now().millisecondsSinceEpoch}.m4a';
    await _recorder.start(const RecordConfig(), path: path);
    setState(() {
      _isRecording = true;
      _recordDuration = Duration.zero;
    });
    _recordTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _recordDuration += const Duration(seconds: 1));
    });
  }

  Future<void> _stopRecordingAndSend() async {
    _recordTimer?.cancel();
    final path = await _recorder.stop();
    if (mounted) setState(() => _isRecording = false);
    if (path != null) {
      await _sendAttachment(path, filename: 'Voice note.m4a');
    }
  }

  Future<void> _cancelRecording() async {
    _recordTimer?.cancel();
    await _recorder.cancel();
    if (mounted) setState(() => _isRecording = false);
  }

  /// Long-press a bubble: edit (sender only) or delete (either side, but
  /// only removes it from *your* view - the backend's delete_message is a
  /// per-side soft delete, not a "delete for everyone").
  Future<void> _showMessageOptions(int index) async {
    final message = _messages[index];
    if (message['id'] == null) return; // not yet confirmed by the server
    final outgoing = message['direction'] == 'outgoing';
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (_) => Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (outgoing)
              ListTile(
                leading: const Icon(Icons.edit_outlined, color: AppColors.primary),
                title: const Text('Edit', style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w700)),
                onTap: () => Navigator.of(context).pop('edit'),
              ),
            ListTile(
              leading: const Icon(Icons.delete_outline, color: AppColors.danger),
              title: const Text('Delete for me',
                  style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w700)),
              onTap: () => Navigator.of(context).pop('delete'),
            ),
          ],
        ),
      ),
    );
    if (!mounted) return;
    if (action == 'edit') {
      await _editMessageAt(index);
    } else if (action == 'delete') {
      await _deleteMessageAt(index);
    }
  }

  Future<void> _editMessageAt(int index) async {
    final message = _messages[index];
    final controller = TextEditingController(text: (message['body'] ?? '').toString());
    final newBody = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Edit message', style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900)),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLines: 4,
          style: const TextStyle(color: AppColors.textDark),
          decoration: const InputDecoration(border: OutlineInputBorder()),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: Text('Cancel', style: TextStyle(color: AppColors.muted)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, controller.text.trim()),
            child: const Text('Save', style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
    if (newBody == null || newBody.isEmpty || !mounted) return;
    try {
      await editMessage(message['id'].toString(), newBody);
      setState(() => _messages[index] = {...message, 'body': newBody});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not edit: $e'), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  Future<void> _deleteMessageAt(int index) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Delete message?', style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900)),
        content: Text('This removes it from your view only - the other person can still see it.',
            style: TextStyle(color: AppColors.muted)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text('Cancel', style: TextStyle(color: AppColors.muted)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Delete', style: TextStyle(color: AppColors.danger, fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final id = _messages[index]['id'].toString();
    try {
      await deleteMessage(id);
      if (mounted) setState(() => _messages.removeAt(index));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not delete: $e'), backgroundColor: AppColors.danger),
        );
      }
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

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes.toString().padLeft(2, '0');
    final seconds = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
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
                  : RefreshIndicator(
                      onRefresh: _refresh,
                      color: AppColors.primary,
                      child: ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                        itemCount: _messages.length,
                        itemBuilder: (context, index) {
                          final m = _messages[index];
                          final outgoing = m['direction'] == 'outgoing';
                          final attachments = (m['attachments'] ?? []) as List<dynamic>;
                          return GestureDetector(
                            onLongPress: () => _showMessageOptions(index),
                            child: _MessageBubble(
                              body: (m['body'] ?? '').toString(),
                              outgoing: outgoing,
                              time: _formatTime(m['created_at']),
                              isRead: m['is_read'] == true,
                              attachment: attachments.isNotEmpty ? attachments.first as Map<String, dynamic> : null,
                            ),
                          );
                        },
                      ),
                    ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                child: _isRecording ? _buildRecordingBar() : _buildComposeBar(),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildComposeBar() {
    return Row(
      children: [
        IconButton(
          onPressed: _sending ? null : _openAttachSheet,
          icon: Icon(Icons.attach_file, color: AppColors.muted),
        ),
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
            onPressed: _sending ? null : (_hasText ? _send : _startRecording),
            icon: _sending
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : Icon(_hasText ? Icons.send : Icons.mic, color: Colors.white, size: 20),
          ),
        ),
      ],
    );
  }

  Widget _buildRecordingBar() {
    return Row(
      children: [
        IconButton(
          onPressed: _cancelRecording,
          icon: const Icon(Icons.delete_outline, color: AppColors.danger),
        ),
        Expanded(
          child: Row(
            children: [
              const Icon(Icons.fiber_manual_record, color: AppColors.danger, size: 14),
              const SizedBox(width: 8),
              Text(_formatDuration(_recordDuration),
                  style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w700)),
              const SizedBox(width: 8),
              Text('Recording voice note...', style: TextStyle(color: AppColors.muted, fontSize: 12)),
            ],
          ),
        ),
        Container(
          decoration: const BoxDecoration(color: AppColors.primary, shape: BoxShape.circle),
          child: IconButton(
            onPressed: _stopRecordingAndSend,
            icon: const Icon(Icons.check, color: Colors.white),
          ),
        ),
      ],
    );
  }
}

class _AttachOption extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;
  const _AttachOption({required this.icon, required this.label, required this.color, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: color.withValues(alpha: 0.14), shape: BoxShape.circle),
            alignment: Alignment.center,
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(height: 8),
          Text(label, style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w700, fontSize: 12)),
        ],
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final String body;
  final bool outgoing;
  final String time;
  final bool isRead;
  final Map<String, dynamic>? attachment;
  const _MessageBubble({
    required this.body,
    required this.outgoing,
    required this.time,
    required this.isRead,
    this.attachment,
  });

  @override
  Widget build(BuildContext context) {
    final textColor = outgoing ? Colors.white : AppColors.textDark;
    return Align(
      alignment: outgoing ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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
            if (attachment != null) ...[
              _AttachmentPreview(attachment: attachment!, foregroundColor: textColor),
              if (body.isNotEmpty) const SizedBox(height: 6),
            ],
            if (body.isNotEmpty) Text(body, style: TextStyle(color: textColor)),
            if (time.isNotEmpty) ...[
              const SizedBox(height: 4),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(time,
                      style: TextStyle(
                          color: outgoing ? Colors.white.withValues(alpha: 0.75) : AppColors.muted, fontSize: 10)),
                  if (outgoing) ...[
                    const SizedBox(width: 4),
                    // No server "delivered" state exists (only sent/read), so
                    // this is a deliberately simplified 2-state tick: single
                    // check once sent, double blue check once actually read -
                    // never a middle "delivered" tick.
                    Icon(
                      isRead ? Icons.done_all : Icons.check,
                      size: 14,
                      color: isRead ? const Color(0xFF34B7F1) : Colors.white70,
                    ),
                  ],
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _AttachmentPreview extends StatelessWidget {
  final Map<String, dynamic> attachment;
  final Color foregroundColor;
  const _AttachmentPreview({required this.attachment, required this.foregroundColor});

  bool get _isLocal => attachment['local'] == true;
  String get _contentType => (attachment['content_type'] ?? '').toString();
  String get _url => (attachment['url'] ?? '').toString();

  @override
  Widget build(BuildContext context) {
    if (_contentType.startsWith('image/')) {
      final image = _isLocal
          ? Image.file(File(_url), width: 200, height: 200, fit: BoxFit.cover)
          : Image.network(_url, width: 200, height: 200, fit: BoxFit.cover);
      return GestureDetector(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => _ImageViewerScreen(isLocal: _isLocal, source: _url)),
        ),
        child: ClipRRect(borderRadius: BorderRadius.circular(12), child: image),
      );
    }
    if (_contentType.startsWith('audio/')) {
      return _VoiceNoteBubble(isLocal: _isLocal, source: _url, color: foregroundColor);
    }
    if (_contentType.startsWith('video/')) {
      return GestureDetector(
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => _VideoViewerScreen(isLocal: _isLocal, source: _url)),
        ),
        child: Container(
          width: 200,
          height: 130,
          decoration: BoxDecoration(color: Colors.black87, borderRadius: BorderRadius.circular(12)),
          alignment: Alignment.center,
          child: const Icon(Icons.play_circle_fill, color: Colors.white, size: 44),
        ),
      );
    }
    return GestureDetector(
      onTap: () async {
        if (_isLocal) return;
        final uri = Uri.tryParse(_url);
        if (uri != null) await launchUrl(uri, mode: LaunchMode.externalApplication);
      },
      child: Container(
        width: 200,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: foregroundColor == Colors.white ? Colors.white.withValues(alpha: 0.16) : AppColors.cardSoft,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(Icons.insert_drive_file, color: foregroundColor),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                (attachment['name'] ?? 'File').toString(),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: foregroundColor, fontSize: 12, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ImageViewerScreen extends StatelessWidget {
  final bool isLocal;
  final String source;
  const _ImageViewerScreen({required this.isLocal, required this.source});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(backgroundColor: Colors.black, foregroundColor: Colors.white, elevation: 0),
      body: Center(
        child: InteractiveViewer(
          child: isLocal ? Image.file(File(source)) : Image.network(source),
        ),
      ),
    );
  }
}

class _VideoViewerScreen extends StatefulWidget {
  final bool isLocal;
  final String source;
  const _VideoViewerScreen({required this.isLocal, required this.source});

  @override
  State<_VideoViewerScreen> createState() => _VideoViewerScreenState();
}

class _VideoViewerScreenState extends State<_VideoViewerScreen> {
  late final VideoPlayerController _controller = widget.isLocal
      ? VideoPlayerController.file(File(widget.source))
      : VideoPlayerController.networkUrl(Uri.parse(widget.source));
  bool _ready = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller.initialize().then((_) {
      if (!mounted) return;
      setState(() => _ready = true);
      _controller.play();
    }).catchError((e) {
      if (mounted) setState(() => _error = e.toString());
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(backgroundColor: Colors.black, foregroundColor: Colors.white, elevation: 0),
      body: Center(
        child: _error != null
            ? Text(_error!, style: const TextStyle(color: Colors.white))
            : _ready
                ? AnimatedBuilder(
                    animation: _controller,
                    builder: (context, _) => AspectRatio(
                      aspectRatio: _controller.value.aspectRatio == 0 ? 16 / 9 : _controller.value.aspectRatio,
                      child: Stack(
                        alignment: Alignment.bottomCenter,
                        children: [
                          VideoPlayer(_controller),
                          Positioned.fill(
                            child: GestureDetector(
                              onTap: () {
                                _controller.value.isPlaying ? _controller.pause() : _controller.play();
                              },
                              child: AnimatedOpacity(
                                opacity: _controller.value.isPlaying ? 0 : 1,
                                duration: const Duration(milliseconds: 200),
                                child: Container(
                                  color: Colors.black26,
                                  alignment: Alignment.center,
                                  child: const Icon(Icons.play_arrow, color: Colors.white, size: 56),
                                ),
                              ),
                            ),
                          ),
                          VideoProgressIndicator(_controller, allowScrubbing: true, padding: const EdgeInsets.all(8)),
                        ],
                      ),
                    ),
                  )
                : const CircularProgressIndicator(color: Colors.white),
      ),
    );
  }
}

class _VoiceNoteBubble extends StatefulWidget {
  final bool isLocal;
  final String source;
  final Color color;
  const _VoiceNoteBubble({required this.isLocal, required this.source, required this.color});

  @override
  State<_VoiceNoteBubble> createState() => _VoiceNoteBubbleState();
}

class _VoiceNoteBubbleState extends State<_VoiceNoteBubble> {
  final _player = AudioPlayer();
  bool _playing = false;
  Duration _duration = Duration.zero;
  Duration _position = Duration.zero;

  @override
  void initState() {
    super.initState();
    _player.onPlayerStateChanged.listen((state) {
      if (mounted) setState(() => _playing = state == PlayerState.playing);
    });
    _player.onDurationChanged.listen((d) {
      if (mounted) setState(() => _duration = d);
    });
    _player.onPositionChanged.listen((p) {
      if (mounted) setState(() => _position = p);
    });
    _player.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _position = Duration.zero);
    });
  }

  @override
  void dispose() {
    _player.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    if (_playing) {
      await _player.pause();
    } else {
      await _player.play(widget.isLocal ? DeviceFileSource(widget.source) : UrlSource(widget.source));
    }
  }

  String _fmt(Duration d) {
    final minutes = d.inMinutes.toString().padLeft(2, '0');
    final seconds = (d.inSeconds % 60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    final shown = _position > Duration.zero ? _position : _duration;
    return SizedBox(
      width: 190,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
            icon: Icon(_playing ? Icons.pause_circle_filled : Icons.play_circle_fill,
                size: 34, color: widget.color),
            onPressed: _toggle,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                LinearProgressIndicator(
                  value: _duration.inMilliseconds == 0 ? 0 : _position.inMilliseconds / _duration.inMilliseconds,
                  minHeight: 3,
                  color: widget.color,
                  backgroundColor: widget.color.withValues(alpha: 0.25),
                ),
                const SizedBox(height: 4),
                Text('Voice note · ${_fmt(shown)}',
                    style: TextStyle(color: widget.color, fontSize: 11)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
