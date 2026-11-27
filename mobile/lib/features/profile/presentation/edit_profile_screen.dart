import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/providers.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/state_views.dart';
import '../../../shared/widgets/validators.dart';
import '../../authentication/presentation/auth_controller.dart';
import '../../authentication/presentation/form_submit.dart';
import 'profile_screen.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});
  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> with FormSubmit {
  late final TextEditingController _first;
  late final TextEditingController _last;
  bool _avatarBusy = false;
  Object? _avatarError;

  @override
  void initState() {
    super.initState();
    final u = ref.read(authControllerProvider).user!;
    _first = TextEditingController(text: u.firstName);
    _last = TextEditingController(text: u.lastName);
  }

  @override
  void dispose() {
    _first.dispose();
    _last.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final ok = await submit(() => ref.read(authControllerProvider.notifier).updateProfile(firstName: _first.text, lastName: _last.text));
    if (ok && mounted) {
      showSuccess(context, ref.read(stringsProvider).t('profile.saved'));
      context.pop();
    }
  }

  Future<void> _pickAvatar(ImageSource source) async {
    final file = await ImagePicker().pickImage(source: source, maxWidth: 1600, imageQuality: 85);
    if (file == null) return;
    setState(() {
      _avatarBusy = true;
      _avatarError = null;
    });
    try {
      final user = await ref.read(authRepositoryProvider).uploadAvatar(file.path);
      ref.read(authControllerProvider.notifier).setUser(user);
    } catch (e) {
      if (mounted) setState(() => _avatarError = e);
    } finally {
      if (mounted) setState(() => _avatarBusy = false);
    }
  }

  Future<void> _removeAvatar() async {
    setState(() {
      _avatarBusy = true;
      _avatarError = null;
    });
    try {
      ref.read(authControllerProvider.notifier).setUser(await ref.read(authRepositoryProvider).removeAvatar());
    } catch (e) {
      if (mounted) setState(() => _avatarError = e);
    } finally {
      if (mounted) setState(() => _avatarBusy = false);
    }
  }

  void _avatarSheet() {
    final s = ref.read(stringsProvider);
    final hasAvatar = ref.read(authControllerProvider).user?.avatarUrl != null;
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (c) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(LucideIcons.image), title: Text(s.t('profile.avatar.gallery')), onTap: () { Navigator.pop(c); _pickAvatar(ImageSource.gallery); }),
          ListTile(leading: const Icon(LucideIcons.camera), title: Text(s.t('profile.avatar.camera')), onTap: () { Navigator.pop(c); _pickAvatar(ImageSource.camera); }),
          if (hasAvatar) ListTile(leading: const Icon(LucideIcons.trash2), title: Text(s.t('profile.avatar.remove')), onTap: () { Navigator.pop(c); _removeAvatar(); }),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    final v = Validators(s);
    final user = ref.watch(authControllerProvider).user;
    if (user == null) return const SizedBox.shrink();
    final e = error;
    return Scaffold(
      appBar: AppBar(title: Text(s.t('profile.edit'))),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Center(
                  child: Semantics(
                    button: true,
                    label: s.t('profile.avatar.change'),
                    child: GestureDetector(
                      onTap: _avatarBusy ? null : _avatarSheet,
                      child: Stack(alignment: Alignment.center, children: [
                        UserAvatar(user: user, size: 96),
                        if (_avatarBusy) const CircularProgressIndicator(),
                        if (!_avatarBusy) Positioned(right: 0, bottom: 0, child: Container(padding: const EdgeInsets.all(6), decoration: const BoxDecoration(color: AppColors.accent, shape: BoxShape.circle), child: const Icon(LucideIcons.camera, size: 16, color: AppColors.primary))),
                      ]),
                    ),
                  ),
                ),
                if (_avatarError != null) ...[const SizedBox(height: 12), FormError(s.error(_avatarError!))],
                const SizedBox(height: AppSpacing.lg),
                Form(
                  key: formKey,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    if (e != null && e.kind != AppErrorKind.validation) ...[FormError(s.error(e)), const SizedBox(height: 16)],
                    AppTextField(controller: _first, label: s.t('auth.firstName'), icon: LucideIcons.user, validator: v.required, serverError: fieldError('first_name')),
                    const SizedBox(height: 16),
                    AppTextField(controller: _last, label: s.t('auth.lastName'), icon: LucideIcons.user, textInputAction: TextInputAction.done, validator: v.required, onSubmitted: (_) => _save(), serverError: fieldError('last_name')),
                    const SizedBox(height: 24),
                    AppButton(label: s.t('common.save'), onPressed: _save, loading: busy),
                  ]),
                ),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
