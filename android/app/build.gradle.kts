import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "com.giveaway.viewer"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.giveaway.viewer"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        buildConfigField("String", "TG_API_ID", "\"${localProps.getProperty("TG_API_ID", "")}\"")
        buildConfigField("String", "TG_API_HASH", "\"${localProps.getProperty("TG_API_HASH", "")}\"")

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }

    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    kotlinOptions {
        jvmTarget = "1.8"
    }
}

chaquopy {
    defaultConfig {
        version = "3.12"
        buildPython("D:/telethon/.tools/py312/tools/python.exe")
        pip {
            install("fastapi==0.100.1")
            install("starlette==0.27.0")
            install("pydantic==1.10.17")
            install("uvicorn==0.30.0")
            install("telethon==1.43.2")
            install("python-dotenv==1.0.1")
            install("h11")
            install("anyio")
            install("pyaes")
        }
    }
}

// Copy the backend + frontend into the Chaquopy python source dir before every build
val syncBackend by tasks.registering(Copy::class) {
    from("../../backend") {
        include("*.py")
    }
    from("../../frontend") {
        into("frontend")
    }
    into("src/main/python")
}
tasks.matching { it.name == "preBuild" || it.name.endsWith("PythonSources") }
    .configureEach { dependsOn(syncBackend) }

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
}
