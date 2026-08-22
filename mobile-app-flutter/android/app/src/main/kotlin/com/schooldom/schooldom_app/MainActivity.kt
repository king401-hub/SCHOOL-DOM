package com.schooldom.schooldom_app

import io.flutter.embedding.android.FlutterFragmentActivity

// local_auth's Android biometric prompt (BiometricPrompt API) requires a
// FragmentActivity - plain FlutterActivity causes authenticate() to fail
// silently/throw, which is why biometric unlock wasn't working at all.
class MainActivity : FlutterFragmentActivity()
