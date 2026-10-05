package com.topwise.cloudpos.aidl.printer

import android.os.Parcel
import android.os.Parcelable

/**
 * Minimal stand-in for com.topwise.cloudpos.aidl.printer.PrinterMessage, needed
 * only so AidlPrinter.getPrinterMessage() has a resolvable return type - this
 * app never calls that diagnostic method, so the exact field write order
 * (unlike PrintItemObj/PrintCuttingMode) was not verified against the real
 * class and must not be relied on.
 */
class PrinterMessage() : Parcelable {
    var printerGray: Int = 0
    var printerTemperature: Int = 0
    var printerVoltage: Int = 0
    var printerMileage: Long = 0
    var printerCount: Int = 0

    private constructor(parcel: Parcel) : this() {
        printerGray = parcel.readInt()
        printerTemperature = parcel.readInt()
        printerVoltage = parcel.readInt()
        printerMileage = parcel.readLong()
        printerCount = parcel.readInt()
    }

    override fun writeToParcel(dest: Parcel, flags: Int) {
        dest.writeInt(printerGray)
        dest.writeInt(printerTemperature)
        dest.writeInt(printerVoltage)
        dest.writeLong(printerMileage)
        dest.writeInt(printerCount)
    }

    override fun describeContents(): Int = 0

    companion object CREATOR : Parcelable.Creator<PrinterMessage> {
        override fun createFromParcel(parcel: Parcel): PrinterMessage = PrinterMessage(parcel)
        override fun newArray(size: Int): Array<PrinterMessage?> = arrayOfNulls(size)
    }
}
