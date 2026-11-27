import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing. The keystore and its passwords live OUTSIDE the repository: point MEBELCHI_KEY_PROPERTIES at a key.properties file
// (storeFile, storePassword, keyAlias, keyPassword) or put android/key.properties there (git-ignored). Never commit either.
val keyPropsFile: File = System.getenv("MEBELCHI_KEY_PROPERTIES")?.takeIf { it.isNotBlank() }?.let { file(it) } ?: rootProject.file("key.properties")
val keyProps = Properties().apply { if (keyPropsFile.exists()) keyPropsFile.inputStream().use { load(it) } }

// TEST build (never for users): MEBELCHI_TEST_BUILD=1 installs next to the real app as "Mebelchi AI Test" (uz.mebelchi.app.test) and may talk
// to a plain-http backend on the developer's own network. Production builds keep cleartext traffic off.
val testBuild = System.getenv("MEBELCHI_TEST_BUILD") == "1"

android {
    namespace = "uz.mebelchi.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // Fixed for the life of the app: Android and Google Play identify the app (and allow updates) by this id.
        applicationId = "uz.mebelchi.app"
        manifestPlaceholders["appLabel"] = if (testBuild) "Mebelchi AI Test" else "Mebelchi AI"
        manifestPlaceholders["usesCleartext"] = if (testBuild) "true" else "false"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (keyPropsFile.exists()) {
                storeFile = file(keyProps.getProperty("storeFile"))
                storePassword = keyProps.getProperty("storePassword")
                keyAlias = keyProps.getProperty("keyAlias")
                keyPassword = keyProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        debug {
            // development builds install next to the production app and are labelled "Dev"
            applicationIdSuffix = ".dev"
            versionNameSuffix = "-dev"
            manifestPlaceholders["appLabel"] = "Mebelchi AI Dev"
            manifestPlaceholders["usesCleartext"] = "true"
        }
        release {
            // A release is never signed with the debug key: without a keystore the build stops here.
            if (!keyPropsFile.exists() && gradle.startParameter.taskNames.any { it.contains("Release", ignoreCase = true) }) {
                throw GradleException("Release signing is not configured: set MEBELCHI_KEY_PROPERTIES to a key.properties file (see mobile/README.md).")
            }
            if (keyPropsFile.exists()) signingConfig = signingConfigs.getByName("release")
            if (testBuild) {
                applicationIdSuffix = ".test"
                versionNameSuffix = "-test"
            }
        }
    }
}

flutter {
    source = "../.."
}
