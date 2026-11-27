/// Build-time configuration. Pass `--dart-define=API_BASE_URL=https://example.com/api/v1` for real builds.
/// The default is the deployed server on Render; for a local Django on the host use --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1 (debug).
class Env {
  Env._();

  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'https://mebelchi-backend.onrender.com/api/v1');

  /// Only a TEST build (tool/release_android.sh with TEST_BUILD=1) may talk plain http; the id suffix and label keep it apart from the real app.
  static const bool testBuild = bool.fromEnvironment('MEBELCHI_TEST_BUILD');

  /// Release builds must never talk plain http, except an explicit test build.
  static bool isSecureOrDebug(String url, {required bool isRelease, bool test = testBuild}) => !isRelease || test || url.startsWith('https://');

  /// The backend returns file links relative to its own origin (`/api/v1/users/1/avatar/?sig=...`).
  static String resolveUrl(String path, {String base = apiBaseUrl}) {
    if (path.startsWith('http://') || path.startsWith('https://')) return path;
    final b = Uri.parse(base);
    return b.replace(path: path.split('?').first, query: path.contains('?') ? path.split('?').skip(1).join('?') : null).toString();
  }
}
