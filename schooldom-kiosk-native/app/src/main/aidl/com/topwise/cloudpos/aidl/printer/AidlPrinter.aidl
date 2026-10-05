package com.topwise.cloudpos.aidl.printer;

import android.graphics.Bitmap;
import com.topwise.cloudpos.aidl.printer.PrintItemObj;
import com.topwise.cloudpos.aidl.printer.PrintCuttingMode;
import com.topwise.cloudpos.aidl.printer.PrinterMessage;
import com.topwise.cloudpos.aidl.printer.AidlPrinterListener;

// Mirrors the real com.topwise.cloudpos.aidl.printer.AidlPrinter interface
// bundled on Topwise CloudPOS terminals (com.android.topwise.topusdkservice).
// There is no public SDK jar for this vendor, so this was recreated by
// pulling the installed TOPUSDKService.apk off the device via adb and
// reverse engineering it with dexdump: the interface's own method list is
// alphabetized by dexdump, but the real AidlPrinter$Stub's TRANSACTION_*
// constants reveal the true declaration order below (1=getPrinterState,
// 2=printText, ... 33=isPosPrinterCoverOpen). aidl assigns transaction
// codes by declaration order, so this order must match exactly for the
// generated Proxy to speak the same wire protocol as the real Stub -
// methods this app never calls are still declared, just to keep every
// later method's transaction number correctly aligned.
interface AidlPrinter {
    int getPrinterState();
    void printText(in List<PrintItemObj> items, AidlPrinterListener listener);
    void printBmp(int x, int y, int width, in Bitmap bitmap, AidlPrinterListener listener);
    void printBarCode(int x, int y, int width, int height, String data, AidlPrinterListener listener);
    void printQrCode(int x, int y, int width, String data, AidlPrinterListener listener);
    void setPrinterGray(int gray);
    int open();
    void close();
    void addText(int x, int y, int width, String text);
    void addBarcode(int x, int y, String data, int width, int height);
    void addQRCode(int x, int y, String data);
    void addImage(int x, in Bitmap bitmap);
    void addImageFile(int x, String path);
    void addLineFeed(int lines);
    void start(AidlPrinterListener listener);
    boolean resetQueue();
    boolean addRuiText(in List<PrintItemObj> items);
    boolean addRuiImage(in Bitmap bitmap, int x);
    boolean addRuiBarCode(String data, int x, int width, int height);
    boolean addRuiQRCode(String data, int x, int width);
    boolean addHuifuImage(in Bitmap bitmap, int x, int y, int width);
    void printRuiQueue(AidlPrinterListener listener);
    void goPaper(int lines);
    void printEnhancedText(in List<PrintItemObj> items, AidlPrinterListener listener);
    int printBuf(in byte[] buf);
    long getClearPrinterMileage(int type);
    int getPrinterGray();
    PrinterMessage getPrinterMessage();
    int cuttingPaper(in PrintCuttingMode mode);
    int printRollback(int type);
    int setPrintLedState(boolean on, int type);
    int getPosPrintPaperState();
    boolean isPosPrinterCoverOpen();
}
