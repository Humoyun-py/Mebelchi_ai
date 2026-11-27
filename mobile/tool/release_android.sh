#!/usr/bin/env bash
# Builds the signed production APK, verifies its signature and writes it with a SHA-256 file to mobile/dist/.
#
#   API_BASE_URL=https://your-domain/api/v1 MEBELCHI_KEY_PROPERTIES=~/.mebelchi-signing/key.properties tool/release_android.sh
#
# Version name and number come from `version: x.y.z+N` in pubspec.yaml (N = Android versionCode; it must grow with every release).
# TEST_BUILD=1 makes a local test build (plain http allowed, id uz.mebelchi.app.test, "Mebelchi AI Test"): never give it to users.
# Set SKIP_TESTS=1 to skip analyze/test. Nothing is uploaded: publishing is a separate, deliberate step (printed at the end).
set -euo pipefail
cd "$(dirname "$0")/.."

: "${API_BASE_URL:?set API_BASE_URL to the https address of the API, e.g. https://example.com/api/v1}"
TEST_BUILD="${TEST_BUILD:-}"
if [ -n "$TEST_BUILD" ]; then
  case "$API_BASE_URL" in http://*|https://*) ;; *) echo "API_BASE_URL must start with http:// or https://" >&2; exit 1 ;; esac
  export MEBELCHI_TEST_BUILD=1
else
  case "$API_BASE_URL" in https://*) ;; *) echo "API_BASE_URL must start with https:// for a release build (use TEST_BUILD=1 for a local test build)" >&2; exit 1 ;; esac
fi
KEYPROPS="${MEBELCHI_KEY_PROPERTIES:-android/key.properties}"
[ -f "$KEYPROPS" ] || { echo "Signing is not configured: $KEYPROPS not found (set MEBELCHI_KEY_PROPERTIES)" >&2; exit 1; }
export MEBELCHI_KEY_PROPERTIES="$(cd "$(dirname "$KEYPROPS")" && pwd)/$(basename "$KEYPROPS")"

ver_line="$(grep -E '^version:' pubspec.yaml | head -1 | awk '{print $2}')"
NAME="${ver_line%%+*}"; CODE="${ver_line##*+}"
[[ "$NAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && "$CODE" =~ ^[0-9]+$ ]] || { echo "pubspec version must look like 1.2.3+4 (found '$ver_line')" >&2; exit 1; }

if [ -z "${SKIP_TESTS:-}" ]; then
  flutter pub get >/dev/null
  flutter analyze
  flutter test
fi

# phones only (arm64 + arm32): the x86 build exists only for emulators and would add about a third to the download
if [ -n "$TEST_BUILD" ]; then
  # test builds also include x86_64 so they run on the emulator
  flutter build apk --release --target-platform android-arm64,android-arm,android-x64 --dart-define=API_BASE_URL="$API_BASE_URL" --dart-define=MEBELCHI_TEST_BUILD=true
else
  flutter build apk --release --target-platform android-arm64,android-arm --dart-define=API_BASE_URL="$API_BASE_URL"
fi
SRC=build/app/outputs/flutter-apk/app-release.apk
[ -f "$SRC" ] || { echo "build did not produce $SRC" >&2; exit 1; }

# apksigner is a Java tool: use the JDK that Flutter itself reports when java is not on PATH
if ! command -v java >/dev/null 2>&1; then
  JAVA_BIN="$(flutter doctor -v 2>/dev/null | sed -n 's/.*Java binary at: //p' | head -1)"
  [ -n "$JAVA_BIN" ] && PATH="$(dirname "$JAVA_BIN"):$PATH"
fi
command -v java >/dev/null 2>&1 || { echo "java not found (needed by apksigner)" >&2; exit 1; }
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}}"
APKSIGNER="$(ls -d "$SDK"/build-tools/*/apksigner 2>/dev/null | sort -V | tail -1 || true)"
[ -n "$APKSIGNER" ] || { echo "apksigner not found under $SDK/build-tools" >&2; exit 1; }
"$APKSIGNER" verify --verbose "$SRC" | grep -E "Verifies|Verified using" || { echo "APK signature did not verify" >&2; exit 1; }
CERT="$("$APKSIGNER" verify --print-certs "$SRC" | grep -m1 "certificate DN")"
if echo "$CERT" | grep -qi "Android Debug"; then echo "Refusing: the APK is signed with the debug key" >&2; exit 1; fi

mkdir -p dist
OUT="dist/mebelchi-ai-$NAME-$CODE${TEST_BUILD:+-test}.apk"
cp "$SRC" "$OUT"
( cd dist && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256" )
echo
echo "Built:    $OUT ($(du -h "$OUT" | cut -f1))"
echo "Signer:   $CERT"
echo "SHA-256:  $(cut -d' ' -f1 "$OUT.sha256")"
echo
echo "To publish on the server (run in the backend container or virtualenv, after copying the APK there):"
echo "  python manage.py publish_android_release --apk $(basename "$OUT") --app-version $NAME --code $CODE --notes-file notes.txt --publish"
