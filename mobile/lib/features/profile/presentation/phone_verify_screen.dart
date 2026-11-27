import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/state_views.dart';
import '../../authentication/presentation/auth_controller.dart';
import '../../authentication/presentation/form_submit.dart';

/// Two steps: send an SMS code to the number, then confirm it. The server decides everything (limits, expiry, attempts);
/// if SMS is not configured on the server it answers 503 and that is shown as is.
class PhoneVerifyScreen extends ConsumerStatefulWidget {
  const PhoneVerifyScreen({super.key});
  @override
  ConsumerState<PhoneVerifyScreen> createState() => _PhoneVerifyScreenState();
}

class _PhoneVerifyScreenState extends ConsumerState<PhoneVerifyScreen> with FormSubmit {
  late final TextEditingController _phone;
  final _code = TextEditingController();
  bool _codeSent = false;
  int _wait = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _phone = TextEditingController(text: ref.read(authControllerProvider).user?.phone ?? '');
  }

  @override
  void dispose() {
    _timer?.cancel();
    _phone.dispose();
    _code.dispose();
    super.dispose();
  }

  void _startTimer(int seconds) {
    _timer?.cancel();
    setState(() => _wait = seconds);
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted || _wait <= 1) {
        t.cancel();
        if (mounted) setState(() => _wait = 0);
      } else {
        setState(() => _wait--);
      }
    });
  }

  Future<void> _send() async {
    final s = ref.read(stringsProvider);
    if (_phone.text.trim().isEmpty) {
      setState(() => error = AppException(AppErrorKind.validation, detail: s.t('profile.phone.enter')));
      return;
    }
    late int after;
    final ok = await submit(() async {
      final phone = _phone.text.trim();
      final current = ref.read(authControllerProvider).user;
      if (current != null && current.phone != phone) await ref.read(authControllerProvider.notifier).updateProfile(phone: phone);
      after = await ref.read(authRepositoryProvider).requestPhoneCode(phone);
    });
    if (ok && mounted) {
      setState(() => _codeSent = true);
      _startTimer(after);
    }
  }

  Future<void> _confirm() async {
    final ok = await submit(() async {
      final user = await ref.read(authRepositoryProvider).confirmPhone(_phone.text, _code.text);
      ref.read(authControllerProvider.notifier).setUser(user);
    });
    if (ok && mounted) {
      showSuccess(context, ref.read(stringsProvider).t('profile.phone.verified'));
      context.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final user = ref.watch(authControllerProvider).user;
    final e = error;
    final verified = user?.phoneVerified == true && user?.phone == _phone.text.trim();
    final message = e == null ? null : (e.kind == AppErrorKind.validation ? (e.fields.values.expand((x) => x).firstOrNull ?? (e.detail.isEmpty ? null : e.detail)) : s.error(e));
    return Scaffold(
      appBar: AppBar(title: Text(s.t('profile.phone.verify'))),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Form(
                key: formKey,
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  if (message != null) ...[FormError(message), const SizedBox(height: 16)],
                  AppTextField(
                    controller: _phone,
                    label: s.t('profile.phone'),
                    hint: s.t('profile.phone.hint'),
                    icon: LucideIcons.phone,
                    keyboardType: TextInputType.phone,
                    enabled: !_codeSent,
                    textInputAction: TextInputAction.done,
                  ),
                  const SizedBox(height: 16),
                  if (verified)
                    Row(children: [const Icon(LucideIcons.check, color: AppColors.success), const SizedBox(width: 8), Text(s.t('profile.phone.verified'))])
                  else if (!_codeSent)
                    AppButton(label: s.t('profile.phone.sendCode'), onPressed: _send, loading: busy)
                  else ...[
                    Text(s.t('profile.phone.codeSent'), style: const TextStyle(color: AppColors.textMuted)),
                    const SizedBox(height: 12),
                    AppTextField(controller: _code, label: s.t('profile.phone.code'), icon: LucideIcons.key, keyboardType: TextInputType.number, textInputAction: TextInputAction.done, onSubmitted: (_) => _confirm(), validator: (v) => (v ?? '').trim().isEmpty ? s.t('auth.required') : null),
                    const SizedBox(height: 16),
                    AppButton(label: s.t('profile.phone.confirm'), onPressed: _confirm, loading: busy),
                    const SizedBox(height: 8),
                    TextButton(onPressed: _wait > 0 || busy ? null : _send, child: Text(_wait > 0 ? s.f('profile.phone.resendIn', {'s': '$_wait'}) : s.t('profile.phone.sendCode'))),
                  ],
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
