import '../../core/l10n/strings.dart';

class Validators {
  Validators(this.s);
  final S s;

  String? required(String? v) => (v == null || v.trim().isEmpty) ? s.t('auth.required') : null;

  String? email(String? v) {
    if (v == null || v.trim().isEmpty) return s.t('auth.required');
    return RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(v.trim()) ? null : s.t('auth.invalidEmail');
  }

  String? password(String? v) {
    if (v == null || v.isEmpty) return s.t('auth.required');
    return v.length < 8 ? s.t('auth.passwordShort') : null;
  }

  String? Function(String?) match(String Function() other) => (v) => v != other() ? s.t('auth.passwordMismatch') : null;
}
