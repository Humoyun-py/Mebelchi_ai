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

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});
  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> with FormSubmit {
  final _first = TextEditingController();
  final _last = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();

  @override
  void dispose() {
    for (final c in [_first, _last, _email, _phone, _password, _confirm]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _go() => submit(() => ref.read(authControllerProvider.notifier).register(
        firstName: _first.text,
        lastName: _last.text,
        email: _email.text,
        password: _password.text,
        phone: _phone.text,
      ));

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final v = Validators(s);
    final e = error;
    final banner = e == null ? null : (e.kind == AppErrorKind.validation ? generalError({'first_name', 'last_name', 'email', 'phone', 'password', 'confirm_password'}) : s.error(e));
    return AuthScaffold(
      title: s.t('auth.register.title'),
      subtitle: s.t('auth.register.subtitle'),
      showBack: true,
      children: [
        Form(
          key: formKey,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (banner != null) ...[FormError(banner), const SizedBox(height: 16)],
            AppTextField(controller: _first, label: s.t('auth.firstName'), icon: LucideIcons.user, autofillHints: const [AutofillHints.givenName], validator: v.required, serverError: fieldError('first_name')),
            const SizedBox(height: 16),
            AppTextField(controller: _last, label: s.t('auth.lastName'), icon: LucideIcons.user, autofillHints: const [AutofillHints.familyName], validator: v.required, serverError: fieldError('last_name')),
            const SizedBox(height: 16),
            AppTextField(controller: _email, label: s.t('auth.email'), icon: LucideIcons.mail, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.email], validator: v.email, serverError: fieldError('email')),
            const SizedBox(height: 16),
            AppTextField(controller: _phone, label: s.t('auth.phoneOptional'), hint: s.t('profile.phone.hint'), icon: LucideIcons.phone, keyboardType: TextInputType.phone, autofillHints: const [AutofillHints.telephoneNumber], serverError: fieldError('phone')),
            const SizedBox(height: 16),
            AppTextField(controller: _password, label: s.t('auth.password'), icon: LucideIcons.lock, obscure: true, autofillHints: const [AutofillHints.newPassword], validator: v.password, serverError: fieldError('password')),
            const SizedBox(height: 16),
            AppTextField(controller: _confirm, label: s.t('auth.confirmPassword'), icon: LucideIcons.lock, obscure: true, textInputAction: TextInputAction.done, validator: v.match(() => _password.text), onSubmitted: (_) => _go(), serverError: fieldError('confirm_password')),
            const SizedBox(height: 24),
            AppButton(label: s.t('auth.register.button'), onPressed: _go, loading: busy),
            const SizedBox(height: 16),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Flexible(child: Text(s.t('auth.haveAccount'))),
              TextButton(onPressed: () => context.go('/login'), child: Text(s.t('auth.login.button'))),
            ]),
          ]),
        ),
      ],
    );
  }
}
