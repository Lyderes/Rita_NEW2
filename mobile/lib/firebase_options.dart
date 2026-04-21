// firebase_options.dart — generated manually to support --dart-define injection.
//
// Run your Flutter web app with:
//   flutter run -d chrome \
//     --dart-define=FIREBASE_API_KEY=<your-api-key> \
//     --dart-define=FIREBASE_AUTH_DOMAIN=<your-project>.firebaseapp.com \
//     --dart-define=FIREBASE_PROJECT_ID=<your-project> \
//     --dart-define=FIREBASE_STORAGE_BUCKET=<your-project>.appspot.com \
//     --dart-define=FIREBASE_MESSAGING_SENDER_ID=<sender-id> \
//     --dart-define=FIREBASE_APP_ID=<app-id> \
//     --dart-define=FIREBASE_VAPID_KEY=<vapid-key>
//
// Or create a .env.firebase file and pass --dart-define-from-file=.env.firebase.
//
// If Firebase is not configured yet, the app runs without push notifications.
// All fields below default to empty strings; Firebase.initializeApp() will
// throw if any required field is empty — which is caught in main.dart.

import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart' show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) return web;
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      default:
        throw UnsupportedError(
          'DefaultFirebaseOptions: unsupported platform — run flutterfire configure.',
        );
    }
  }

  static const FirebaseOptions web = FirebaseOptions(
    apiKey: String.fromEnvironment('FIREBASE_API_KEY'),
    authDomain: String.fromEnvironment('FIREBASE_AUTH_DOMAIN'),
    projectId: String.fromEnvironment('FIREBASE_PROJECT_ID'),
    storageBucket: String.fromEnvironment('FIREBASE_STORAGE_BUCKET'),
    messagingSenderId: String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID'),
    appId: String.fromEnvironment('FIREBASE_APP_ID'),
    measurementId: String.fromEnvironment('FIREBASE_MEASUREMENT_ID'),
  );

  // Placeholders — run `flutterfire configure` to generate real values.
  static const FirebaseOptions android = FirebaseOptions(
    apiKey: String.fromEnvironment('FIREBASE_API_KEY'),
    appId: String.fromEnvironment('FIREBASE_APP_ID'),
    messagingSenderId: String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID'),
    projectId: String.fromEnvironment('FIREBASE_PROJECT_ID'),
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: String.fromEnvironment('FIREBASE_API_KEY'),
    appId: String.fromEnvironment('FIREBASE_APP_ID'),
    messagingSenderId: String.fromEnvironment('FIREBASE_MESSAGING_SENDER_ID'),
    projectId: String.fromEnvironment('FIREBASE_PROJECT_ID'),
    iosBundleId: String.fromEnvironment('FIREBASE_IOS_BUNDLE_ID'),
  );
}
