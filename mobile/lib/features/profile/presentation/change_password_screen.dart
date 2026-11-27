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
import '../../../shared/widgets/validators.dart';
import '../../authentication/presentation/form_submit.dart';

class ChangePasswordScreen extends ConsumerStatefulWidget {
  const ChangePasswordScreen({super.key});
  @override
  ConsumerState<ChangePasswordScreen> createState() => _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends ConsumerState<ChangePasswordScreen> with FormSubmit {
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final ok = await submit(() => ref.read(authRepositoryProvider).changePassword(current: _current.text, next: _next.text));
    if (ok && mounted) {
      showSuccess(context, ref.read(stringsProvider).t('profile.password.changed'));
      context.pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final v = Validators(s);
    final e = error;
    final banner = e == null ? null : (e.kind == AppErrorKind.validation ? generalError({'current_password', 'new_password'}) : s.error(e));
    return Scaffold(
      appBar: AppBar(title: Text(s.t('profile.password'))),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Form(
                key: formKey,
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  if (banner != null) ...[FormError(banner), const SizedBox(height: 16)],
                  AppTextField(controller: _current, label: s.t('profile.password.current'), icon: LucideIcons.lock, obscure: true, validator: v.required, serverError: fieldError('current_password')),
                  const SizedBox(height: 16),
                  AppTextField(controller: _next, label: s.t('profile.password.new'), icon: LucideIcons.lock, obscure: true, validator: v.password, serverError: fieldError('new_password')),
                  const SizedBox(height: 16),
                  AppTextField(controller: _confirm, label: s.t('auth.confirmPassword'), icon: LucideIcons.lock, obscure: true, textInputAction: TextInputAction.done, validator: v.match(() => _next.text), onSubmitted: (_) => _save()),
                  const SizedBox(height: 24),
                  AppButton(label: s.t('common.save'), onPressed: _save, loading: busy),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
