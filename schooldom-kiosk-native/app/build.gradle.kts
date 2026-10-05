import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Release signing lives in key.properties (repo root of this project),
// gitignored - never commit it or the keystore it points to. Copied over
// from the Flutter kiosk app's own android/key.properties: same fleet, same
// terminals, same signing constraints documented below.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystorePropertiesFile.inputStream().use { keystoreProperties.load(it) }
}

android {
    namespace = "com.schooldom.schooldom_scanner_kiosk"
    compileSdk = 35

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
        applicationId = "com.schooldom.schooldom_scanner_kiosk"
        // The fleet's confirmed oldest terminal runs Android 7.0 (API 24) -
        // see device_fleet notes. Never raise this without checking the
        // fleet's actual installed OS versions first.
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0-native"
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
            signingConfig = if (keystorePropertiesFile.exists()) signingConfigs.getByName("fleet") else signingConfigs.getByName("debug")
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

// Zero external dependencies, on purpose. This machine has no network access
// to Google's Maven repo (only a few pre-approved hosts resolve), and every
// androidx library tried here (core, appcompat, material, security-crypto)
// transitively needs lifecycle-runtime/fragment/activity/etc., none of which
// are cached - androidx.core alone pulls in lifecycle-runtime:2.6.2, which
// is missing too. Rather than chase an inconsistent partial cache, this app
// uses only the Android SDK and the Kotlin stdlib bundled with the Kotlin
// Gradle plugin (already proven to resolve - it's what compiles
// TopwisePrinterBridge.kt/LocalSmsBridge.kt in the Flutter app's own build).
// Plain android.app.Activity, HttpURLConnection, LocationManager, and
// SharedPreferences cover everything AppCompat/Material/core/OkHttp/Play
// Services Location would have - and it also means genuinely zero library
// footprint on terminals already overloaded by Google Play Services.
dependencies {
}
