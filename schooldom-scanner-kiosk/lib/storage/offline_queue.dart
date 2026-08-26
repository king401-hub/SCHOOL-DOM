import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

const _kQueue = 'offline_queue';

typedef QueueItem = Map<String, dynamic>;

Future<List<QueueItem>> readQueue() async {
  final prefs = await SharedPreferences.getInstance();
  final raw = prefs.getString(_kQueue);
  if (raw == null) return [];
  try {
    return (jsonDecode(raw) as List).cast<QueueItem>();
  } catch (_) {
    return [];
  }
}

Future<void> writeQueue(List<QueueItem> queue) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(_kQueue, jsonEncode(queue));
}

Future<void> enqueue(QueueItem item) async {
  final queue = await readQueue();
  queue.add({...item, 'queuedAt': DateTime.now().toIso8601String()});
  await writeQueue(queue);
}
