# The recreated Topwise CloudPOS printer AIDL classes must keep their exact
# names. PrintItemObj.ALIGN crosses the AIDL boundary via
# Parcel.writeValue()/readValue()'s generic Serializable fallback, which
# resolves the receiving class BY ITS FULLY QUALIFIED NAME inside the real
# service's own process (com.android.topwise.topusdkservice) - a process
# that has no knowledge of this app's R8 renaming table. Without this rule,
# R8 was renaming PrintItemObj$ALIGN to a short name like `f1.d`, and the
# real service's own ObjectInputStream then threw ClassNotFoundException
# trying to resolve "f1.d" (confirmed live via logcat's JavaBinder trace).
-keep class com.topwise.cloudpos.aidl.printer.** { *; }
