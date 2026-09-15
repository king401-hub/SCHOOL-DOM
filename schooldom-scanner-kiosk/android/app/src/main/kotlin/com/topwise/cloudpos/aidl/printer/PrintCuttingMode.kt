package com.topwise.cloudpos.aidl.printer

import android.os.Parcel
import android.os.Parcelable

/**
 * Reimplementation of com.topwise.cloudpos.aidl.printer.PrintCuttingMode.
 * The real type is a Parcelable enum with a single int `mode` field; disassembly
 * of its <clinit> confirmed CUTTING_MODE_HALT -> mode=0, CUTTING_MODE_FULL -> mode=1,
 * and its writeToParcel writes exactly that one int. Reimplemented here as a
 * plain Parcelable (not a Kotlin enum) since only the wire format - not local
 * identity - needs to match for the AidlPrinter Proxy to talk to the real Stub.
 */
class PrintCuttingMode private constructor(val mode: Int) : Parcelable {

    private constructor(parcel: Parcel) : this(parcel.readInt())

    override fun writeToParcel(dest: Parcel, flags: Int) {
        dest.writeInt(mode)
    }

    override fun describeContents(): Int = 0

    companion object {
        @JvmField val CUTTING_MODE_HALT = PrintCuttingMode(0)
        @JvmField val CUTTING_MODE_FULL = PrintCuttingMode(1)

        @JvmField
        val CREATOR: Parcelable.Creator<PrintCuttingMode> = object : Parcelable.Creator<PrintCuttingMode> {
            override fun createFromParcel(parcel: Parcel): PrintCuttingMode = PrintCuttingMode(parcel)
            override fun newArray(size: Int): Array<PrintCuttingMode?> = arrayOfNulls(size)
        }
    }
}
