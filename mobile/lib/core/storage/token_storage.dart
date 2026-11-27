import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class Tokens {
  const Tokens({required this.access, required this.refresh});
  final String access;
  final String refresh;

  @override
  bool operator ==(Object other) => other is Tokens && other.access == access && other.refresh == refresh;
  @override
  int get hashCode => Object.hash(access, refresh);
}

abstract class TokenStorage {
  Future<Tokens?> read();
  Future<void> write(Tokens tokens);
  Future<void> clear();
}

/// Tokens live in the Android keystore-backed secure storage, never in plain preferences.
class SecureTokenStorage implements TokenStorage {
  SecureTokenStorage([FlutterSecureStorage? storage]) : _s = storage ?? const FlutterSecureStorage();
  final FlutterSecureStorage _s;
  static const _a = 'mebelchi.access';
  static const _r = 'mebelchi.refresh';

  @override
  Future<Tokens?> read() async {
    final a = await _s.read(key: _a);
    final r = await _s.read(key: _r);
    if (a == null || r == null || a.isEmpty || r.isEmpty) return null;
    return Tokens(access: a, refresh: r);
  }

  @override
  Future<void> write(Tokens t) async {
    await _s.write(key: _a, value: t.access);
    await _s.write(key: _r, value: t.refresh);
  }

  @override
  Future<void> clear() async {
    await _s.delete(key: _a);
    await _s.delete(key: _r);
  }
}

class MemoryTokenStorage implements TokenStorage {
  Tokens? _t;
  @override
  Future<Tokens?> read() async => _t;
  @override
  Future<void> write(Tokens tokens) async => _t = tokens;
  @override
  Future<void> clear() async => _t = null;
}
