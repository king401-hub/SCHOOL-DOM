import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing (the Topwise key) lives in android/key.properties, which
// is gitignored - never commit it or the .jks it points to.
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

        // Topwise's own shared SDK-distribution signing key (the same one in
        // their official TopUsdkTestDemo and EmvDemo sample projects). The
        // Topwise T1 terminal's "topwise verity" install-time check rejects an
        // APK signed with any other key, debug key included
        // (INSTALL_PARSE_FAILED_NO_CERTIFICATES), and Android only accepts an
        // in-place update signed with the SAME key as the installed app - so
        // releases must always be signed with this one. v1-only with v2 off
        // mirrors exactly how Topwise's own demo project signs (their firmware
        // does not support V2 signing). The keystore and its passwords come
        // from android/key.properties (gitignored - never commit either).
        create("topwise") {
            if (keystorePropertiesFile.exists()) {
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
            enableV1Signing = true
            enableV2Signing = false
            enableV3Signing = false
            enableV4Signing = false
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("topwise")
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
            "Release builds must be signed with the Topwise key (the terminals reject " +
                "anything else), but android/key.properties is missing. Restore it, and the " +
                "topwise.jks it points to, from the backup before building a release."
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
