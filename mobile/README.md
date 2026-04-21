# RITA Mobile — Flutter Web Dashboard

The caregiver dashboard for RITA, built with Flutter Web for cross-platform compatibility.

## Prerequisites

- [Flutter SDK](https://docs.flutter.dev/get-started/install) (latest stable)
- Chrome browser (for web testing)
- Backend running at `http://localhost:8000`

## Firebase Configuration

Push notifications and messaging are optional. To enable Firebase:

1. **Copy the Firebase configuration file:**
   ```powershell
   Copy-Item .env.firebase.example .env.firebase
   ```

2. **Add your Firebase credentials to `.env.firebase`:**
   ```
   FIREBASE_API_KEY=your_api_key
   FIREBASE_AUTH_DOMAIN=your_auth_domain
   FIREBASE_PROJECT_ID=your_project_id
   FIREBASE_STORAGE_BUCKET=your_storage_bucket
   FIREBASE_MESSAGING_SENDER_ID=your_sender_id
   FIREBASE_APP_ID=your_app_id
   ```

   > **⚠️ Security:** Never commit `.env.firebase` to version control. It's automatically ignored by `.gitignore`.

3. **Run the app with Firebase enabled:**
   ```powershell
   .\scripts\run-mobile.ps1 -Mode web
   ```

   The `--dart-define-from-file=.env.firebase` flag is automatically applied by the script.

## Running the App

### Web (Local Development)

```powershell
.\scripts\run-mobile.ps1 -Mode web
```

- Opens at `http://127.0.0.1:5173` (default)
- Hot reload enabled
- Backend assumed at `http://localhost:8000`

### Android

```powershell
.\scripts\run-mobile.ps1 -Mode android
```

(Requires Android SDK / emulator or connected device)

### Other Commands

```powershell
# Fetch dependencies
.\scripts\run-mobile.ps1 -Mode get

# Run tests
.\scripts\run-mobile.ps1 -Mode test

# Check Flutter setup
.\scripts\run-mobile.ps1 -Mode doctor
```

## Architecture & References

- **Main app entry:** `lib/main.dart`
- **Firebase setup:** `lib/firebase_options.dart`
- **Global state:** `lib/app/` (Riverpod providers)
- **Backend endpoints:** Talk to FastAPI server at port 8000

For more details, see [RITA Architecture](/docs/architecture.md).

