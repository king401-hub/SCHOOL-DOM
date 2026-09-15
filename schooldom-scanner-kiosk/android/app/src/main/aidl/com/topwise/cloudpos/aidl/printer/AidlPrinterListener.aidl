package com.topwise.cloudpos.aidl.printer;

// Mirrors the real system-service interface bundled on Topwise CloudPOS
// terminals (com.android.topwise.topusdkservice). Recreated by reverse
// engineering the installed TOPUSDKService.apk (dexdump) - there is no
// public SDK jar for this vendor. Method order matters: aidl assigns
// transaction codes by declaration order, and it must match the real
// Stub's TRANSACTION_onError=1 / TRANSACTION_onPrintFinish=2.
interface AidlPrinterListener {
    void onError(int code);
    void onPrintFinish();
}
