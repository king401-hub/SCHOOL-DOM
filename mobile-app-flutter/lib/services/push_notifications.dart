import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../api/endpoints.dart';

/// Push notifications via Firebase Cloud Messaging - Android only for now
/// (iOS push needs an APNs key, which requires a paid Apple Developer
/// account this project doesn't have; there's also no GoogleService-Info.plist
/// wired in, so Firebase itself never even initializes on iOS builds).
///
/// Three delivery states:
///  - App backgrounded/closed: FCM shows the system notification itself
///    using the `notification` block the backend always sends - no code
///    needed here at all.
///  - App in foreground: FCM does NOT auto-display anything in this state,
///    so onMessage below shows a local notification manually.
///  - Notification tapped from background/terminated: just brings the app
///    to the foreground for now - deep-linking to a specific screen per
///    notification type is a reasonable v2, not done here.
class PushNotifications {
  PushNotifications._();

  static final FlutterLocalNotificationsPlugin _local = FlutterLocalNotificationsPlugin();
  static const AndroidNotificationChannel _channel = AndroidNotificationChannel(
    'schooldom_default',
    'SchoolDom notifications',
    description: 'Messages, exam updates, and other SchoolDom alerts.',
    importance: Importance.high,
  );
  static bool _initialized = false;

  static Future<void> initialize() async {
    if (_initialized) return;
    _initialized = true;
    if (!Platform.isAndroid) return;

    await Firebase.initializeApp();
    FirebaseMessaging.onBackgroundMessage(_backgroundHandler);

    await _local.initialize(
      settings: const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      ),
    );
    await _local
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(_channel);

    FirebaseMessaging.onMessage.listen(_showForegroundNotification);
  }

  static Future<void> _showForegroundNotification(RemoteMessage message) async {
    final notification = message.notification;
    if (notification == null) return;
    await _local.show(
      id: notification.hashCode,
      title: notification.title,
      body: notification.body,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          _channel.id,
          _channel.name,
          channelDescription: _channel.description,
          importance: Importance.high,
          priority: Priority.high,
        ),
      ),
    );
  }

  /// Call once a session is authenticated - requests notification
  /// permission, gets this device's FCM token, and registers it with the
  /// backend (see users/app_views.py `register_mobile_device`, which
  /// previously stored tokens but had nothing reading them back).
  static Future<void> registerToken() async {
    if (!Platform.isAndroid) return;
    try {
      final messaging = FirebaseMessaging.instance;
      final settings = await messaging.requestPermission();
      if (settings.authorizationStatus == AuthorizationStatus.denied) return;
      final token = await messaging.getToken();
      if (token == null) return;
      await registerDevice({'token': token, 'platform': 'android', 'provider': 'fcm'});
    } catch (e) {
      if (kDebugMode) debugPrint('Push token registration failed: $e');
    }
  }
}

@pragma('vm:entry-point')
Future<void> _backgroundHandler(RemoteMessage message) async {
  // FCM already displays the system notification automatically here (the
  // payload always has a `notification` block) - this handler only needs to
  // exist for the plugin to work correctly, no action required.
}
