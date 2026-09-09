package com.schooldom.schooldom_scanner_kiosk

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Screen Pinning (Lock Task Mode without Device Owner) - startLockTask()/
 * stopLockTask() are plain Activity methods, no extra permission or plugin
 * needed. This is the "no factory reset required" kiosk lock level: the
 * first call shows Android's own screen-pinning explainer once, then the
 * app is pinned - exiting needs a deliberate back+recents hold, which pops
 * an "unpin" prompt rather than just returning to the launcher.
 */
class MainActivity : FlutterActivity() {
    private val channel = "com.schooldom.scanner_kiosk/lock_task"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel).setMethodCallHandler { call, result ->
            when (call.method) {
                "startLockTask" -> {
                    try {
                        startLockTask()
                        result.success(true)
                    } catch (e: Exception) {
                        result.success(false)
                    }
                }
                "stopLockTask" -> {
                    try {
                        stopLockTask()
                        result.success(true)
                    } catch (e: Exception) {
                        result.success(false)
                    }
                }
                else -> result.notImplemented()
            }
        }
    }
}
