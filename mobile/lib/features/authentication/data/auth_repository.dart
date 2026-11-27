import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../../core/storage/token_storage.dart';
import '../domain/user.dart';

class AuthSession {
  const AuthSession(this.user, this.tokens);
  final User user;
  final Tokens tokens;
}

/// Everything the app needs from `auth/` and `users/me/` on the existing Django API.
class AuthRepository {
  AuthRepository(this._api);
  final ApiClient _api;

  Dio get _dio => _api.dio;

  AuthSession _session(Map data) => AuthSession(
        User.fromJson(Map<String, dynamic>.from(data['user'] as Map)),
        Tokens(access: data['access'] as String, refresh: data['refresh'] as String),
      );

  Future<AuthSession> login(String email, String password) => _api.guard(() async {
        final r = await _dio.post('auth/login/', data: {'email': email.trim(), 'password': password}, options: noAuth);
        return _session(r.data as Map);
      });

  Future<AuthSession> register({
    required String firstName,
    required String lastName,
    required String email,
    required String password,
    String phone = '',
  }) =>
      _api.guard(() async {
        final r = await _dio.post(
          'auth/register/',
          data: {
            'first_name': firstName.trim(),
            'last_name': lastName.trim(),
            'email': email.trim(),
            'phone': phone.trim(),
            'password': password,
            'confirm_password': password,
          },
          options: noAuth,
        );
        return _session(r.data as Map);
      });

  Future<void> logout(String refresh) => _api.guard(() async {
        await _dio.post('auth/logout/', data: {'refresh': refresh});
      });

  Future<void> requestPasswordReset(String email) => _api.guard(() async {
        await _dio.post('auth/password-reset/', data: {'email': email.trim()}, options: noAuth);
      });

  Future<User> me() => _api.guard(() async => User.fromJson(Map<String, dynamic>.from((await _dio.get('users/me/')).data as Map)));

  Future<User> updateProfile({String? firstName, String? lastName, String? phone, String? language}) => _api.guard(() async {
        final body = <String, dynamic>{
          'first_name': ?firstName?.trim(),
          'last_name': ?lastName?.trim(),
          'phone': ?phone?.trim(),
          'language': ?language,
        };
        final r = await _dio.patch('users/me/', data: body);
        return User.fromJson(Map<String, dynamic>.from(r.data as Map));
      });

  Future<User> setRole(UserRole role) => _api.guard(() async {
        final r = await _dio.post('users/me/role/', data: {'role': role.apiValue});
        return User.fromJson(Map<String, dynamic>.from(r.data as Map));
      });

  Future<void> changePassword({required String current, required String next}) => _api.guard(() async {
        await _dio.post('users/me/password/', data: {'current_password': current, 'new_password': next});
      });

  Future<User> uploadAvatar(String path) => _api.guard(() async {
        await _dio.post('users/me/avatar/', data: FormData.fromMap({'avatar': await MultipartFile.fromFile(path)}));
        return User.fromJson(Map<String, dynamic>.from((await _dio.get('users/me/')).data as Map));
      });

  Future<User> removeAvatar() => _api.guard(() async {
        await _dio.delete('users/me/avatar/');
        return User.fromJson(Map<String, dynamic>.from((await _dio.get('users/me/')).data as Map));
      });

  /// Sends an SMS code. The server answers 503 when SMS is not configured; the caller shows that honestly.
  Future<int> requestPhoneCode(String phone) => _api.guard(() async {
        final r = await _dio.post('users/me/phone/request/', data: {'phone': phone.trim()});
        return ((r.data as Map)['resend_after'] as num?)?.toInt() ?? 60;
      });

  Future<User> confirmPhone(String phone, String code) => _api.guard(() async {
        final r = await _dio.post('users/me/phone/confirm/', data: {'phone': phone.trim(), 'code': code.trim()});
        return User.fromJson(Map<String, dynamic>.from(r.data as Map));
      });

  Future<bool> serverReachable() async {
    try {
      final r = await _dio.get('meta/', options: noAuth);
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
