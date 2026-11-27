# Mebelchi AI mobile (Flutter, Android)

Talks only to the existing Django REST API (`/api/v1`). It has no database of its own and no business rules: the server decides.

## Run

```bash
cd mobile
flutter pub get
# Android emulator -> Django dev server on the host (default API_BASE_URL is http://10.0.2.2:8000/api/v1)
flutter run
# real server (release builds REQUIRE https):
flutter run --dart-define=API_BASE_URL=https://example.com/api/v1
```

Cleartext http is allowed in debug builds only (`android/app/src/debug/AndroidManifest.xml`).

## Structure

```
lib/core/        config (Env), errors (AppException), network (ApiClient), storage (secure tokens), theme, l10n (uz/ru/en), providers
lib/features/    authentication, dashboard, profile  (each: data / domain / presentation)
lib/shared/      widgets, models (Paged<T> for DRF lists)
lib/routing/     go_router + the redirect rule (unit-tested)
```

State: Riverpod. HTTP: Dio. Tokens: flutter_secure_storage (Android keystore). Icons: Lucide (vector). No emoji.

## Behaviour worth knowing

- Access token is refreshed once for any number of parallel 401s; the server rotates refresh tokens and blacklists the old one.
- A refresh that fails because of the network keeps the session; a refresh the server rejects signs the user out.
- Logout signs out locally first, then asks the server to blacklist the refresh token (5 s limit), so no network never traps a user.
- Roles: `homeowner` / `maker` are chosen after the first sign-in; `workshop` is assigned by an administrator and never offered. The bottom navigation is the same for every role until a role gets its own screens, and a button is only added when the feature behind it works.
- Phone verification uses the backend SMS endpoints. When SMS is not configured the server answers 503 and the app shows that text.
- Uzbek and Russian texts need review by a native speaker.

## Tests

```bash
flutter analyze && flutter test                          # unit + widget tests
MEBELCHI_E2E_URL=http://127.0.0.1:8000/api/v1 flutter test test/e2e   # real backend (use a throwaway database)
```

The e2e test registers a user, picks a role, edits the profile, forces an expired access token, checks token rotation and that
a rotated or logged-out refresh token is rejected. Auth endpoints are throttled to 10 requests per minute per IP, so restart the dev server between runs.

## Phase 3 (done so far): catalogue and room designer

- **Catalogue** (`features/furniture_catalog`): approved furniture from `furniture/templates/`, category chips, search, detail with the six side photos, size, material, lead time, workshop, and "Add to a room design". Prices are shown exactly as the server sends them; a missing price says so.
- **Room designer** (`features/room_designer`): the server's guided flow (`/rooms/`): room type, optional photo (stored as reference only, not analysed), doors/windows/furniture, size, openings, style, then furnishing. The 3D room is the server-built GLB shown in a WebView (`model_viewer_plus`): orbit and zoom only, **no first-person walking yet**. Move/rotate/resize/remove items, wall and floor colour, floor material, light, finish, share the `.mebelchi` file or a GLB, open a `.mebelchi` file. The first step says plainly that this is a guided assistant, not AI.
- **My Projects** (`features/projects`): list (active/archived, search, load more), create, edit, pin, archive, delete. Calculations and cutting lists attached to a project are shown as counts; creating them is still web-only.
- Not done in Phase 3 (needs the AI provider or later phases): AI chat, room-photo understanding, image-to-3D, first-person walk.

Device test (needs an emulator/phone and a throwaway backend started with `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,10.0.2.2`):
`flutter test integration_test -d <device> --dart-define=API_BASE_URL=http://10.0.2.2:8765/api/v1`

## Release APK (Phase 9)

- Application id `uz.mebelchi.app` (fixed); debug builds are `uz.mebelchi.app.dev` "Mebelchi AI Dev".
- Signing key and passwords live **outside** the repository (`MEBELCHI_KEY_PROPERTIES=/path/key.properties` with `storeFile`, `storePassword`, `keyAlias`, `keyPassword`). A release build without it fails; it is never signed with the debug key.
- Build, verify and checksum: `API_BASE_URL=https://your-domain/api/v1 MEBELCHI_KEY_PROPERTIES=... tool/release_android.sh` (output in `dist/`, git-ignored). The version comes from `version:` in `pubspec.yaml`.
- **Local test build** (backend on your own computer, no server): `TEST_BUILD=1 API_BASE_URL=http://<your-LAN-ip>:8000/api/v1 MEBELCHI_KEY_PROPERTIES=... tool/release_android.sh`. It allows plain http, installs as `uz.mebelchi.app.test` "Mebelchi AI Test" next to the real app, and must never be given to users. The phone must be on the same Wi-Fi; start Django with `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<ip> python manage.py runserver 0.0.0.0:8000` and Vite with `npm run dev -- --host`. If the computer's IP changes, rebuild.
- Publishing on the server and the download page: see `docs/DEPLOYMENT.md` section 11. The app is not on Google Play.
- Android licences must be accepted once for some SDK parts: `flutter doctor --android-licenses`.
