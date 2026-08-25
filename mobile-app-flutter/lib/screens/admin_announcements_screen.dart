import 'package:flutter/material.dart';
import '../api/admin_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';

const _kCategories = {
  'all': 'All',
  'notice': 'Notice',
  'circular': 'Circular',
  'event': 'Event',
};

/// Admin app's Announcements tab - Notice/Circular/Event categories, backed
/// by the new users/app_views.py `announcements_list` / `announcement_create`
/// / `announcement_detail` endpoints (Announcement.category is new too).
class AdminAnnouncementsScreen extends StatefulWidget {
  const AdminAnnouncementsScreen({super.key});

  @override
  State<AdminAnnouncementsScreen> createState() => _AdminAnnouncementsScreenState();
}

class _AdminAnnouncementsScreenState extends State<AdminAnnouncementsScreen> {
  List<dynamic> _items = [];
  bool _loading = true;
  String? _error;
  String _category = 'all';

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
      final data = await loadAnnouncements(category: _category == 'all' ? null : _category);
      setState(() => _items = (data['announcements'] ?? []) as List<dynamic>);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openCreate() async {
    final created = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _AnnouncementForm(),
    );
    if (created == true) _load();
  }

  Future<void> _archive(Map<String, dynamic> item) async {
    try {
      await editAnnouncement(item['id'].toString(), isPublished: false);
      _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Could not archive: $e'), backgroundColor: AppColors.danger));
      }
    }
  }

  Future<void> _delete(Map<String, dynamic> item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Delete announcement?', style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
          TextButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Delete', style: TextStyle(color: AppColors.danger, fontWeight: FontWeight.w800))),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await deleteAnnouncement(item['id'].toString());
      if (mounted) setState(() => _items.removeWhere((a) => a['id'] == item['id']));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Could not delete: $e'), backgroundColor: AppColors.danger));
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
        title: const Text('Announcements', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
      ),
      floatingActionButton: Container(
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(28), gradient: AppGradients.brand),
        child: FloatingActionButton.extended(
          backgroundColor: Colors.transparent,
          elevation: 0,
          onPressed: _openCreate,
          icon: const Icon(Icons.campaign_outlined, color: Colors.white),
          label: const Text('Create Announcement', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
        ),
      ),
      body: SafeArea(
        child: _loading && _items.isEmpty
            ? const SkeletonList()
            : _error != null && _items.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline, color: AppColors.danger, size: 40),
                          const SizedBox(height: 12),
                          const Text("Couldn't load announcements.",
                              style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
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
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 90),
                      children: [
                        SizedBox(
                          height: 36,
                          child: ListView(
                            scrollDirection: Axis.horizontal,
                            children: [
                              for (final entry in _kCategories.entries) ...[
                                _FilterChip(
                                  label: entry.value,
                                  selected: _category == entry.key,
                                  onTap: () => setState(() {
                                    _category = entry.key;
                                    _load();
                                  }),
                                ),
                                const SizedBox(width: 8),
                              ],
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        if (_items.isEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 40),
                            child: Center(
                              child: Text('No announcements yet. Tap below to create one.',
                                  textAlign: TextAlign.center, style: TextStyle(color: AppColors.muted)),
                            ),
                          )
                        else
                          for (final raw in _items) ...[
                            _AnnouncementCard(
                              item: raw as Map<String, dynamic>,
                              onArchive: () => _archive(raw),
                              onDelete: () => _delete(raw),
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

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          gradient: selected ? AppGradients.brand : null,
          color: selected ? null : AppColors.surfaceSoft,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? Colors.transparent : AppColors.border),
        ),
        child: Text(label,
            style: TextStyle(
                color: selected ? Colors.white : AppColors.text, fontWeight: FontWeight.w800, fontSize: 13)),
      ),
    );
  }
}

class _AnnouncementCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final VoidCallback onArchive;
  final VoidCallback onDelete;
  const _AnnouncementCard({required this.item, required this.onArchive, required this.onDelete});

  Color _categoryColor(String category) => switch (category) {
        'circular' => AppColors.warning,
        'event' => AppColors.secondary,
        _ => AppColors.primary,
      };

  @override
  Widget build(BuildContext context) {
    final category = (item['category'] ?? 'notice').toString();
    final published = item['is_published'] != false;
    return AppCard(
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: _categoryColor(category).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(_kCategories[category] ?? category.toUpperCase(),
                  style: TextStyle(color: _categoryColor(category), fontWeight: FontWeight.w800, fontSize: 10)),
            ),
            const Spacer(),
            if (!published)
              Text('ARCHIVED', style: TextStyle(color: AppColors.muted, fontSize: 10, fontWeight: FontWeight.w800)),
            PopupMenuButton<String>(
              icon: Icon(Icons.more_vert, color: AppColors.muted, size: 20),
              onSelected: (v) => v == 'archive' ? onArchive() : onDelete(),
              itemBuilder: (context) => [
                if (published) const PopupMenuItem(value: 'archive', child: Text('Archive')),
                const PopupMenuItem(value: 'delete', child: Text('Delete')),
              ],
            ),
          ],
        ),
        Text((item['title'] ?? 'Announcement').toString(),
            style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900, fontSize: 15)),
        if ((item['summary'] ?? '').toString().isNotEmpty)
          Text(item['summary'].toString(),
              maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
      ],
    );
  }
}

class _AnnouncementForm extends StatefulWidget {
  const _AnnouncementForm();

  @override
  State<_AnnouncementForm> createState() => _AnnouncementFormState();
}

class _AnnouncementFormState extends State<_AnnouncementForm> {
  final _title = TextEditingController();
  final _content = TextEditingController();
  String _category = 'notice';
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _title.dispose();
    _content.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_title.text.trim().isEmpty || _content.text.trim().isEmpty) {
      setState(() => _error = 'Title and content are required.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await createAnnouncement(title: _title.text.trim(), content: _content.text.trim(), category: _category);
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
              const Text('New announcement',
                  style: TextStyle(color: AppColors.textDark, fontSize: 18, fontWeight: FontWeight.w900)),
              const SizedBox(height: 16),
              Row(
                children: [
                  for (final key in const ['notice', 'circular', 'event']) ...[
                    Expanded(
                      child: GestureDetector(
                        onTap: () => setState(() => _category = key),
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            gradient: _category == key ? AppGradients.brand : null,
                            color: _category == key ? null : AppColors.surfaceSoft,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(_kCategories[key]!,
                              style: TextStyle(
                                  color: _category == key ? Colors.white : AppColors.mutedDark,
                                  fontWeight: FontWeight.w800,
                                  fontSize: 12)),
                        ),
                      ),
                    ),
                    if (key != 'event') const SizedBox(width: 8),
                  ],
                ],
              ),
              const SizedBox(height: 14),
              TextField(
                controller: _title,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Title'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _content,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Message', alignLabelWithHint: true),
                maxLines: 5,
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
              ],
              const SizedBox(height: 16),
              PrimaryButton(title: 'Publish', loading: _saving, onPressed: _save),
            ],
          ),
        ),
      ),
    );
  }
}
