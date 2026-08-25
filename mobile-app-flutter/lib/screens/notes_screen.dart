import 'package:flutter/material.dart';
import '../api/teacher_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';

/// Standalone notepad - split out from the old combined Lesson Plans &
/// Notepad screen so Notes can grow into its own productivity tool (search,
/// pin, edit, delete, sorted newest/pinned-first) without crowding the
/// lesson-planning form.
class NotesScreen extends StatefulWidget {
  const NotesScreen({super.key});

  @override
  State<NotesScreen> createState() => _NotesScreenState();
}

class _NotesScreenState extends State<NotesScreen> {
  List<dynamic> _notes = [];
  bool _loading = true;
  bool _initialLoadDone = false;
  String? _error;
  String _search = '';

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
      final data = await loadTeacherNotes();
      setState(() => _notes = (data['notes'] ?? []) as List<dynamic>);
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

  List<dynamic> get _filtered {
    if (_search.trim().isEmpty) return _notes;
    final query = _search.trim().toLowerCase();
    return _notes.where((raw) {
      final note = raw as Map<String, dynamic>;
      return (note['title'] ?? '').toString().toLowerCase().contains(query) ||
          (note['body'] ?? '').toString().toLowerCase().contains(query);
    }).toList();
  }

  Future<void> _openAddNote() async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _NoteForm(),
    );
    if (saved == true) _load();
  }

  Future<void> _togglePin(Map<String, dynamic> note) async {
    final id = note['id'] as int;
    final nextPinned = note['pinned'] != true;
    setState(() => note['pinned'] = nextPinned);
    try {
      await editTeacherNote(id, pinned: nextPinned);
      _load();
    } catch (e) {
      if (mounted) {
        setState(() => note['pinned'] = !nextPinned);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not update: $e'), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  Future<void> _editNote(Map<String, dynamic> note) async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _NoteForm(existing: note),
    );
    if (saved == true) _load();
  }

  Future<void> _deleteNote(Map<String, dynamic> note) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Delete note?', style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900)),
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
    if (confirmed != true) return;
    try {
      await deleteTeacherNote(note['id'] as int);
      if (mounted) setState(() => _notes.removeWhere((n) => n['id'] == note['id']));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not delete: $e'), backgroundColor: AppColors.danger),
        );
      }
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
        title: const Text('Notes', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: AppColors.primary,
        onPressed: _openAddNote,
        child: const Icon(Icons.add, color: Colors.white),
      ),
      body: SafeArea(
        child: !_initialLoadDone && _loading
            ? const SkeletonList()
            : _error != null
                ? _ErrorState(message: _error!, onRetry: _load)
                : BrandedRefresh(
                    onRefresh: _load,
                    showSpinner: _loading,
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                      children: [
                        TextField(
                          style: const TextStyle(color: AppColors.textDark),
                          decoration: InputDecoration(
                            hintText: 'Search notes',
                            prefixIcon: Icon(Icons.search, color: AppColors.muted),
                            contentPadding: const EdgeInsets.symmetric(vertical: 12),
                          ),
                          onChanged: (v) => setState(() => _search = v),
                        ),
                        const SizedBox(height: 16),
                        if (_filtered.isEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 40),
                            child: Center(
                              child: Text(
                                _notes.isEmpty ? 'No notes yet. Tap + to create one.' : 'No notes match your search.',
                                textAlign: TextAlign.center,
                                style: TextStyle(color: AppColors.muted),
                              ),
                            ),
                          )
                        else
                          for (final raw in _filtered) ...[
                            _NoteCard(
                              item: raw as Map<String, dynamic>,
                              onTogglePin: () => _togglePin(raw),
                              onEdit: () => _editNote(raw),
                              onDelete: () => _deleteNote(raw),
                            ),
                            const SizedBox(height: 10),
                          ],
                      ],
                    ),
                  ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: AppColors.danger, size: 40),
            const SizedBox(height: 12),
            const Text("Couldn't load your notes.",
                style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
            const SizedBox(height: 4),
            Text('Check your connection and try again.',
                textAlign: TextAlign.center, style: TextStyle(color: AppColors.muted, fontSize: 13)),
            const SizedBox(height: 16),
            SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: onRetry)),
          ],
        ),
      ),
    );
  }
}

class _NoteCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final VoidCallback onTogglePin;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  const _NoteCard({required this.item, required this.onTogglePin, required this.onEdit, required this.onDelete});

  String _relativeTime(dynamic raw) {
    final dt = DateTime.tryParse((raw ?? '').toString());
    if (dt == null) return '';
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inDays < 1) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final pinned = item['pinned'] == true;
    final term = (item['term'] ?? '').toString();
    return AppCard(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            GestureDetector(
              onTap: onTogglePin,
              child: Icon(pinned ? Icons.push_pin : Icons.push_pin_outlined,
                  size: 18, color: pinned ? AppColors.warning : AppColors.muted),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text((item['title'] ?? 'Note').toString(),
                  style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
            ),
            PopupMenuButton<String>(
              icon: Icon(Icons.more_vert, color: AppColors.muted, size: 20),
              onSelected: (value) => value == 'edit' ? onEdit() : onDelete(),
              itemBuilder: (context) => const [
                PopupMenuItem(value: 'edit', child: Text('Edit')),
                PopupMenuItem(value: 'delete', child: Text('Delete')),
              ],
            ),
          ],
        ),
        if ((item['body'] ?? '').toString().isNotEmpty)
          Text(item['body'].toString(),
              maxLines: 4, overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
        Row(
          children: [
            if (term.isNotEmpty) ...[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: AppColors.primarySoft, borderRadius: BorderRadius.circular(20)),
                child: Text(term, style: const TextStyle(color: AppColors.primary, fontSize: 10, fontWeight: FontWeight.w800)),
              ),
              const SizedBox(width: 8),
            ],
            Text(_relativeTime(item['updated_at']), style: TextStyle(color: AppColors.muted, fontSize: 11)),
          ],
        ),
      ],
    );
  }
}

class _NoteForm extends StatefulWidget {
  final Map<String, dynamic>? existing;
  const _NoteForm({this.existing});

  @override
  State<_NoteForm> createState() => _NoteFormState();
}

class _NoteFormState extends State<_NoteForm> {
  late final _title = TextEditingController(text: (widget.existing?['title'] ?? 'Quick note').toString());
  late final _body = TextEditingController(text: (widget.existing?['body'] ?? '').toString());
  late bool _pinned = widget.existing?['pinned'] == true;
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      if (widget.existing != null) {
        await editTeacherNote(
          widget.existing!['id'] as int,
          title: _title.text.trim(),
          body: _body.text.trim(),
          pinned: _pinned,
        );
      } else {
        await saveTeacherNote(title: _title.text.trim(), body: _body.text.trim(), pinned: _pinned);
      }
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(widget.existing != null ? 'Edit note' : 'New note',
                  style: const TextStyle(color: AppColors.textDark, fontSize: 18, fontWeight: FontWeight.w900)),
              const SizedBox(height: 16),
              TextField(
                controller: _title,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Title'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _body,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Note', alignLabelWithHint: true),
                maxLines: 5,
              ),
              Row(
                children: [
                  Checkbox(
                    value: _pinned,
                    activeColor: AppColors.primary,
                    onChanged: (v) => setState(() => _pinned = v ?? false),
                  ),
                  const Text('Pin this note', style: TextStyle(color: AppColors.mutedDark)),
                ],
              ),
              if (_error != null) ...[
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
                const SizedBox(height: 8),
              ],
              const SizedBox(height: 8),
              PrimaryButton(title: 'Save', loading: _saving, onPressed: _save),
            ],
          ),
        ),
      ),
    );
  }
}
