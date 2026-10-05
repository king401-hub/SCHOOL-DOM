package com.topwise.cloudpos.aidl.printer

import android.os.Parcel
import android.os.Parcelable

/**
 * Reimplementation of the real com.topwise.cloudpos.aidl.printer.PrintItemObj
 * Parcelable, matching the field write order confirmed by disassembling the
 * real class's writeToParcel/<init>(Parcel) in the vendor's TOPUSDKService.apk
 * (dexdump -d): text, fontSize, isBold, align, isUnderline, isWordWrap,
 * lineHeight, letterSpacing, marginLeft. The three booleans and the ALIGN
 * enum are boxed and sent via Parcel.writeValue/readValue rather than
 * writeInt/writeByte - that is what the real class does, so it must be
 * replicated exactly for the generated AidlPrinter Proxy to be wire-compatible
 * with the real Stub running in the system service process.
 *
 * ALIGN is deliberately NOT Parcelable (the real one isn't either - no
 * CREATOR, no writeToParcel on it). It rides inside writeValue's generic
 * Serializable fallback, which Android implements with real
 * java.io.ObjectOutputStream/ObjectInputStream. Java enum serialization only
 * encodes the fully-qualified class name and constant name, not any
 * structural signature, so as long as this class lives at the same package
 * + name (com.topwise.cloudpos.aidl.printer.PrintItemObj$ALIGN) with the
 * same constant names, the real service's own ALIGN class resolves it fine
 * on deserialization - regardless of which process originally wrote it.
 */
class PrintItemObj(
    var text: String?,
    var fontSize: Int = 24,
    var isBold: Boolean = false,
    var align: ALIGN = ALIGN.LEFT,
    var isUnderline: Boolean = false,
    var isWordWrap: Boolean = true,
    var lineHeight: Int = 29,
    var letterSpacing: Int = 0,
    var marginLeft: Int = 0,
) : Parcelable {

    enum class ALIGN { CENTER, LEFT, RIGHT }

    private constructor(parcel: Parcel) : this(
        parcel.readString(),
        parcel.readInt(),
        parcel.readValue(Boolean::class.java.classLoader) as Boolean,
        parcel.readValue(ALIGN::class.java.classLoader) as ALIGN,
        parcel.readValue(Boolean::class.java.classLoader) as Boolean,
        parcel.readValue(Boolean::class.java.classLoader) as Boolean,
        parcel.readInt(),
        parcel.readInt(),
        parcel.readInt(),
    )

    override fun writeToParcel(dest: Parcel, flags: Int) {
        dest.writeString(text)
        dest.writeInt(fontSize)
        dest.writeValue(isBold)
        dest.writeValue(align)
        dest.writeValue(isUnderline)
        dest.writeValue(isWordWrap)
        dest.writeInt(lineHeight)
        dest.writeInt(letterSpacing)
        dest.writeInt(marginLeft)
    }

    override fun describeContents(): Int = 0

    companion object CREATOR : Parcelable.Creator<PrintItemObj> {
        override fun createFromParcel(parcel: Parcel): PrintItemObj = PrintItemObj(parcel)
        override fun newArray(size: Int): Array<PrintItemObj?> = arrayOfNulls(size)
    }
}
