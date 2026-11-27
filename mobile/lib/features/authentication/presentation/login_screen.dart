import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/providers.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/state_views.dart';
import '../../../shared/widgets/validators.dart';
import 'auth_controller.dart';
import 'auth_scaffold.dart';
import 'form_submit.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> with FormSubmit {
  final _email = TextEditingController();
  final _password = TextEditingController();

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _go() => submit(() => ref.read(authControllerProvider.notifier).login(_email.text, _password.text));

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final v = Validators(s);
    final e = error;
    final banner = e == null ? null : (e.kind == AppErrorKind.unauthorized ? s.t('auth.badCredentials') : (generalError({'email', 'password'}) ?? (e.kind == AppErrorKind.validation ? null : s.error(e))));
    return AuthScaffold(
      title: s.t('auth.login.title'),
      subtitle: s.t('auth.login.subtitle'),
      children: [
        Form(
          key: formKey,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (banner != null) ...[FormError(banner), const SizedBox(height: 16)],
            AppTextField(controller: _email, label: s.t('auth.email'), icon: LucideIcons.mail, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.email], validator: v.email, serverError: fieldError('email')),
            const SizedBox(height: 16),
            AppTextField(controller: _password, label: s.t('auth.password'), icon: LucideIcons.lock, obscure: true, textInputAction: TextInputAction.done, autofillHints: const [AutofillHints.password], validator: v.required, onSubmitted: (_) => _go(), serverError: fieldError('password')),
            Align(alignment: Alignment.centerRight, child: TextButton(onPressed: () => context.push('/forgot'), child: Text(s.t('auth.forgot')))),
            const SizedBox(height: 8),
            AppButton(label: s.t('auth.login.button'), onPressed: _go, loading: busy),
            const SizedBox(height: 24),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Flexible(child: Text(s.t('auth.noAccount'))),
              TextButton(onPressed: () => context.go('/register'), child: Text(s.t('auth.register.button'))),
            ]),
          ]),
        ),
      ],
    );
  }
}
