import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/providers.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/state_views.dart';
import '../../../shared/widgets/validators.dart';
import 'auth_scaffold.dart';
import 'form_submit.dart';

class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key});
  @override
  ConsumerState<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> with FormSubmit {
  final _email = TextEditingController();
  bool _sent = false;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _go() async {
    final ok = await submit(() => ref.read(authRepositoryProvider).requestPasswordReset(_email.text));
    if (ok && mounted) setState(() => _sent = true);
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final v = Validators(s);
    final e = error;
    return AuthScaffold(
      title: s.t('auth.forgot.title'),
      subtitle: s.t('auth.forgot.subtitle'),
      showBack: true,
      children: [
        if (_sent)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(color: const Color(0xFFECFDF5), borderRadius: BorderRadius.circular(12), border: Border.all(color: const Color(0xFFA7F3D0))),
            child: Row(children: [
              const Icon(LucideIcons.check, color: Color(0xFF047857)),
              const SizedBox(width: 12),
              Expanded(child: Text(s.t('auth.forgot.sent'))),
            ]),
          )
        else
          Form(
            key: formKey,
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              if (e != null && e.kind != AppErrorKind.validation) ...[FormError(s.error(e)), const SizedBox(height: 16)],
              AppTextField(controller: _email, label: s.t('auth.email'), icon: LucideIcons.mail, keyboardType: TextInputType.emailAddress, textInputAction: TextInputAction.done, validator: v.email, onSubmitted: (_) => _go(), serverError: fieldError('email')),
              const SizedBox(height: 24),
              AppButton(label: s.t('auth.forgot.send'), onPressed: _go, loading: busy),
            ]),
          ),
      ],
    );
  }
}
