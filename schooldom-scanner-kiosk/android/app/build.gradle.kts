import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing lives in android/key.properties, which is gitignored -
// never commit it or the keystore it points to.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystorePropertiesFile.inputStream().use { keystoreProperties.load(it) }
}

android {
    namespace = "com.schooldom.schooldom_scanner_kiosk"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    // Needed for the hand-recreated Topwise CloudPOS printer AIDL interfaces
    // under src/main/aidl - AGP defaults this to off.
    buildFeatures {
        aidl = true
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.schooldom.schooldom_scanner_kiosk"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        getByName("debug") {
            // v3/v4 signing blocks confuse the cert-collection step on at
            // least one older (2019 security patch) Topwise terminal
            // (INSTALL_PARSE_FAILED_NO_CERTIFICATES: "... using APK
            // Signature Scheme v2 ... using topwise verity") - forcing
            // v1+v2-only for maximum compatibility with old firmware.
            enableV1Signing = true
            enableV2Signing = true
            enableV3Signing = false
            enableV4Signing = false
        }

        // The key the fleet's installed terminals are signed with. Android only
        // accepts an in-place update signed with the SAME key as the installed
        // app (and uninstalling instead would log the school out), so this must
        // match what is on the terminals - every one checked so far (three
        // Topwise T1 and a T2N, Android 7 to 11) runs an app signed with the
        // old PC's Android debug key, so releases are signed with that key: one
        // APK then updates every model. The keystore and its passwords come from
        // android/key.properties (gitignored - never commit either).
        //
        // v1 + v2 both on: v2 is required by Android 11+ for this targetSdk and
        // is understood from Android 7, while v3/v4 blocks confuse the older
        // Topwise terminals' installer. A key whose terminals' firmware cannot
        // take v2 (Topwise's own shared SDK key - the T1's "topwise verity"
        // check is fussy about signatures) can set `v2Signing=false` there.
        create("fleet") {
            if (keystorePropertiesFile.exists()) {
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
            enableV1Signing = true
            enableV2Signing = keystoreProperties.getProperty("v2Signing", "true").toBoolean()
            enableV3Signing = false
            enableV4Signing = false
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("fleet")
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}

// Without the keystore a release build would fail obscurely - and must never
// fall back to signing with some other key, which terminals would then reject.
gradle.taskGraph.whenReady {
    val releaseBuild = allTasks.any {
        it.name == "assembleRelease" || it.name == "bundleRelease" || it.name == "packageRelease"
    }
    if (releaseBuild && !keystorePropertiesFile.exists()) {
        throw GradleException(
            "Release builds must be signed with the key the terminals already carry (they " +
                "reject an update signed with any other), but android/key.properties is " +
                "missing. Restore it, and the keystore it points to, from the backup " +
                "before building a release."
        )
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
