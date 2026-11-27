import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'config/env.dart';
import 'l10n/strings.dart';
import 'network/api_client.dart';
import 'storage/token_storage.dart';
import '../features/authentication/data/auth_repository.dart';
import '../features/authentication/presentation/auth_controller.dart';

/// Overridden in `main()` with the real instance (and in tests with a fake one).
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) => throw UnimplementedError('sharedPreferencesProvider must be overridden'));

final tokenStorageProvider = Provider<TokenStorage>((ref) => SecureTokenStorage());

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient(
      storage: ref.watch(tokenStorageProvider),
      baseUrl: Env.apiBaseUrl,
      onSessionExpired: () => ref.read(authControllerProvider.notifier).sessionExpired(),
    ));

final authRepositoryProvider = Provider<AuthRepository>((ref) => AuthRepository(ref.watch(apiClientProvider)));

/// Interface language, chosen on the device (default: the phone's language when supported, otherwise Uzbek).
class LanguageController extends Notifier<String> {
  static const _key = 'mebelchi.language';

  @override
  String build() {
    final saved = ref.read(sharedPreferencesProvider).getString(_key);
    return supportedLanguages.contains(saved) ? saved! : 'uz';
  }

  Future<void> set(String lang) async {
    if (!supportedLanguages.contains(lang)) return;
    state = lang;
    await ref.read(sharedPreferencesProvider).setString(_key, lang);
  }
}

final languageProvider = NotifierProvider<LanguageController, String>(LanguageController.new);

final stringsProvider = Provider<S>((ref) => S(ref.watch(languageProvider)));
