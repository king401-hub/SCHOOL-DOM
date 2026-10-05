package com.schooldom.schooldom_scanner_kiosk

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import android.os.Parcel
import com.topwise.cloudpos.aidl.printer.AidlPrinter
import com.topwise.cloudpos.aidl.printer.AidlPrinterListener
import com.topwise.cloudpos.aidl.printer.PrintCuttingMode
import com.topwise.cloudpos.aidl.printer.PrintItemObj
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Talks to the Topwise CloudPOS thermal printer on this kiosk's hardware.
 *
 * There is no public SDK jar for Topwise's terminals - only a system app,
 * com.android.topwise.topusdkservice, that exposes the real printer over a
 * bound AIDL service. This bridge binds to it directly and calls through
 * the AidlPrinter interface recreated (via dexdump reverse engineering of
 * the installed TOPUSDKService.apk) in com.topwise.cloudpos.aidl.printer.
 *
 * The sunmi_printer_plus plugin this app used to use targets Sunmi hardware
 * specifically and throws `lateinit property configPrinter has not been
 * initialized` on this Topwise device - it can never work here, hence this
 * hand-rolled replacement.
 */
class TopwisePrinterBridge(context: Context) {
    private val appContext = context.applicationContext
    private val worker = Executors.newSingleThreadExecutor()

    @Volatile private var printer: AidlPrinter? = null
    @Volatile private var connectLatch: CountDownLatch? = null
    private val bindLock = Object()

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder) {
            printer = try {
                val printerBinder = fetchPrinterBinder(binder)
                if (printerBinder != null) AidlPrinter.Stub.asInterface(printerBinder) else null
            } catch (e: Throwable) {
                null
            }
            connectLatch?.countDown()
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            printer = null
        }
    }

    /**
     * DeviceService (the exported entry point) returns an AidlDeviceService
     * binder, not the printer directly - getPrinter() on it hands back a
     * second IBinder for the printer sub-service. Called with a raw
     * transact() (interface token + transaction code 8, both confirmed via
     * dexdump against AidlDeviceService$Stub) rather than a full recreated
     * AidlDeviceService.aidl, since that interface has ~39 methods and only
     * this one is needed here.
     */
    private fun fetchPrinterBinder(deviceServiceBinder: IBinder): IBinder? {
        val data = Parcel.obtain()
        val reply = Parcel.obtain()
        return try {
            data.writeInterfaceToken(DEVICE_SERVICE_DESCRIPTOR)
            deviceServiceBinder.transact(TRANSACTION_GET_PRINTER, data, reply, 0)
            reply.readException()
            reply.readStrongBinder()
        } finally {
            data.recycle()
            reply.recycle()
        }
    }

    /** Blocking - must be called from [worker], never the calling app's main thread. */
    private fun ensureConnectedBlocking(): AidlPrinter? {
        printer?.let { return it }
        synchronized(bindLock) {
            printer?.let { return it }
            val latch = CountDownLatch(1)
            connectLatch = latch
            val intent = Intent(DEVICE_SERVICE_ACTION).apply { setPackage(DEVICE_SERVICE_PACKAGE) }
            val bound = try {
                appContext.bindService(intent, connection, Context.BIND_AUTO_CREATE)
            } catch (e: Throwable) {
                false
            }
            if (!bound) return null
            latch.await(5, TimeUnit.SECONDS)
            return printer
        }
    }

    fun isAvailable(callback: (Boolean) -> Unit) {
        worker.execute {
            val p = ensureConnectedBlocking()
            val ok = if (p == null) {
                false
            } else {
                try {
                    p.getPrinterState()
                    true
                } catch (e: Throwable) {
                    false
                }
            }
            callback(ok)
        }
    }

    fun printFeeReminder(
        schoolName: String,
        studentName: String,
        studentClass: String,
        studentId: String,
        paid: String,
        outstanding: String,
        accountNumber: String,
        bankName: String,
        accountName: String,
        dateText: String,
        callback: (Boolean, String?) -> Unit,
    ) {
        worker.execute {
            val p = ensureConnectedBlocking()
            if (p == null) {
                callback(false, "printer_unavailable")
                return@execute
            }
            try {
                p.open()

                // fontSize=24 (the PrintItemObj default) rendered far too
                // large on this hardware's 58mm paper (~16 chars/line
                // instead of the usual ~32) - halved throughout.
                val items = ArrayList<PrintItemObj>()
                items.add(PrintItemObj(schoolName, fontSize = 18, isBold = true, align = PrintItemObj.ALIGN.CENTER))
                items.add(PrintItemObj("Fee Reminder", fontSize = 14, isBold = true, align = PrintItemObj.ALIGN.CENTER))
                items.add(PrintItemObj(" ", fontSize = 14))
                items.add(PrintItemObj("Name: $studentName", fontSize = 14))
                items.add(PrintItemObj("Class: $studentClass", fontSize = 14))
                items.add(PrintItemObj("Student ID: $studentId", fontSize = 14))
                items.add(PrintItemObj(" ", fontSize = 14))
                items.add(PrintItemObj("Fees Paid: $paid", fontSize = 14))
                items.add(PrintItemObj("Outstanding: $outstanding", fontSize = 14))
                if (accountNumber.isNotBlank()) {
                    items.add(PrintItemObj(" ", fontSize = 14))
                    items.add(PrintItemObj("Pay to:", fontSize = 14, isBold = true))
                    items.add(PrintItemObj(accountNumber, fontSize = 14))
                    if (accountName.isNotBlank()) {
                        items.add(PrintItemObj(accountName, fontSize = 14))
                    }
                    if (bankName.isNotBlank()) {
                        items.add(PrintItemObj(bankName, fontSize = 14))
                    }
                }
                items.add(PrintItemObj(" ", fontSize = 14))
                items.add(PrintItemObj(dateText, fontSize = 12, align = PrintItemObj.ALIGN.CENTER))

                val printLatch = CountDownLatch(1)
                var printError: String? = null
                val listener = object : AidlPrinterListener.Stub() {
                    override fun onError(code: Int) {
                        printError = "print_error_$code"
                        printLatch.countDown()
                    }

                    override fun onPrintFinish() {
                        printLatch.countDown()
                    }
                }

                p.printText(items, listener)
                printLatch.await(15, TimeUnit.SECONDS)
                p.addLineFeed(20)
                p.cuttingPaper(PrintCuttingMode.CUTTING_MODE_FULL)
                callback(printError == null, printError)
            } catch (e: Throwable) {
                callback(false, e.message ?: "print_failed")
            }
        }
    }

    companion object {
        private const val DEVICE_SERVICE_ACTION = "topwise_cloudpos_device_service"
        private const val DEVICE_SERVICE_PACKAGE = "com.android.topwise.topusdkservice"
        private const val DEVICE_SERVICE_DESCRIPTOR = "com.topwise.cloudpos.aidl.AidlDeviceService"

        // AidlDeviceService$Stub.TRANSACTION_getPrinter, confirmed via dexdump.
        private const val TRANSACTION_GET_PRINTER = IBinder.FIRST_CALL_TRANSACTION + 7
    }
}
