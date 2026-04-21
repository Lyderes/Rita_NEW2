// firebase-messaging-sw.js — FCM background message handler for Flutter Web.
//
// This service worker runs outside the Flutter context and must use plain JS.
// Firebase config values here are PUBLIC (same values in your web app's JS
// bundle) — it is safe and normal to commit them.
//
// Fill in your project's values below, or use a build-time substitution step
// (e.g. `envsubst`) to inject them from environment variables.
//
// Required values can be found in:
//   Firebase Console → Project Settings → Your apps → Web app → Config

importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

// ---------------------------------------------------------------------------
// Firebase project config — replace placeholders with your project values.
// ---------------------------------------------------------------------------
const firebaseConfig = {
  apiKey:            'AIzaSyDdtXD_XwhBkewvoPW80Ias0gF_tYOurys',
  authDomain:        'rita-caregiving.firebaseapp.com',
  projectId:         'rita-caregiving',
  storageBucket:     'rita-caregiving.firebasestorage.app',
  messagingSenderId: '709971628329',
  appId:             '1:709971628329:web:7e94e869f7c7910332a738',
};

// Only initialise if config looks real (prevents noisy errors during local dev
// without Firebase credentials).
if (firebaseConfig.apiKey && !firebaseConfig.apiKey.startsWith('REPLACE_')) {
  firebase.initializeApp(firebaseConfig);

  const messaging = firebase.messaging();

  // Handle background messages (app in background / closed tab).
  messaging.onBackgroundMessage((payload) => {
    const title   = payload.notification?.title  ?? 'RITA';
    const options = {
      body: payload.notification?.body ?? '',
      icon: '/icons/Icon-192.png',
      badge: '/icons/Icon-192.png',
      data: payload.data ?? {},
    };
    return self.registration.showNotification(title, options);
  });
}
