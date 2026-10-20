import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Same fleet, same terminals, same signing constraints as
// schooldom-kiosk-native - see that project's build.gradle.kts for the
// full story on the signing key. Reuses the identical key.properties/
// keystore so a terminal that already trusts the kiosk app's signer
// doesn't need anything new to install this one too.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystorePropertiesFile.inputStream().use { keystoreProperties.load(it) }
}

android {
    namespace = "com.schooldom.cardassign"
    compileSdk = 35

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.schooldom.cardassign"
        // The fleet's confirmed oldest terminal runs Android 7.0 (API 24) -
        // this app is meant to run on the exact same terminals as the
        // attendance kiosk, so it matches that floor.
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }

    signingConfigs {
        getByName("debug") {
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

// Zero external dependencies, same reasoning as schooldom-kiosk-native: no
// network access on this machine to fetch anything from Maven beyond what
// the Kotlin Gradle plugin itself already resolves. Plain
// android.app.Activity, HttpURLConnection, and the NFC reader-mode APIs
// cover everything this app needs.
dependencies {
}
