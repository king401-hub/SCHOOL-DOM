package com.schooldom.schooldom_scanner_kiosk

import android.os.Handler
import android.os.Looper
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val channelName = "schooldom/topwise_printer"
    private val mainHandler = Handler(Looper.getMainLooper())
    private lateinit var printerBridge: TopwisePrinterBridge

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        printerBridge = TopwisePrinterBridge(applicationContext)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName).setMethodCallHandler { call, result ->
            when (call.method) {
                "isAvailable" -> printerBridge.isAvailable { available ->
                    mainHandler.post { result.success(available) }
                }

                "printFeeReminder" -> {
                    val args = call.arguments as? Map<*, *>
                    if (args == null) {
                        result.error("bad_args", "Missing arguments", null)
                        return@setMethodCallHandler
                    }
                    printerBridge.printFeeReminder(
                        schoolName = args["schoolName"] as? String ?: "",
                        studentName = args["studentName"] as? String ?: "",
                        studentClass = args["studentClass"] as? String ?: "",
                        studentId = args["studentId"] as? String ?: "",
                        paid = args["paid"] as? String ?: "",
                        outstanding = args["outstanding"] as? String ?: "",
                        accountNumber = args["accountNumber"] as? String ?: "",
                        bankName = args["bankName"] as? String ?: "",
                        accountName = args["accountName"] as? String ?: "",
                        dateText = args["dateText"] as? String ?: "",
                    ) { success, error ->
                        mainHandler.post {
                            if (success) {
                                result.success(true)
                            } else {
                                result.error("print_failed", error ?: "Unknown printer error", null)
                            }
                        }
                    }
                }

                else -> result.notImplemented()
            }
        }
    }
}
