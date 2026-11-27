import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/providers.dart';

class AppTextField extends ConsumerStatefulWidget {
  const AppTextField({
    super.key,
    required this.controller,
    required this.label,
    this.icon,
    this.obscure = false,
    this.keyboardType,
    this.textInputAction = TextInputAction.next,
    this.validator,
    this.serverError,
    this.autofillHints,
    this.onSubmitted,
    this.inputFormatters,
    this.enabled = true,
    this.hint,
  });

  final TextEditingController controller;
  final String label;
  final String? hint;
  final IconData? icon;
  final bool obscure;
  final TextInputType? keyboardType;
  final TextInputAction textInputAction;
  final String? Function(String?)? validator;
  final String? serverError;
  final Iterable<String>? autofillHints;
  final ValueChanged<String>? onSubmitted;
  final List<TextInputFormatter>? inputFormatters;
  final bool enabled;

  @override
  ConsumerState<AppTextField> createState() => _AppTextFieldState();
}

class _AppTextFieldState extends ConsumerState<AppTextField> {
  bool _hidden = true;
  String? _errorFor; // the text the server complained about; the message disappears once the user edits it

  @override
  void didUpdateWidget(AppTextField old) {
    super.didUpdateWidget(old);
    if (widget.serverError != old.serverError) _errorFor = widget.controller.text;
  }

  @override
  Widget build(BuildContext context) {
    final s = ref.watch(stringsProvider);
    return TextFormField(
      controller: widget.controller,
      enabled: widget.enabled,
      obscureText: widget.obscure && _hidden,
      keyboardType: widget.keyboardType,
      textInputAction: widget.textInputAction,
      autofillHints: widget.autofillHints,
      inputFormatters: widget.inputFormatters,
      onFieldSubmitted: widget.onSubmitted,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      validator: (v) => widget.validator?.call(v) ?? (widget.serverError != null && v == _errorFor ? widget.serverError : null),
      decoration: InputDecoration(
        labelText: widget.label,
        hintText: widget.hint,
        errorText: null,
        prefixIcon: widget.icon == null ? null : Icon(widget.icon, size: 20),
        suffixIcon: widget.obscure
            ? IconButton(
                tooltip: _hidden ? s.t('auth.showPassword') : s.t('auth.hidePassword'),
                icon: Icon(_hidden ? LucideIcons.eye : LucideIcons.eyeOff, size: 20),
                onPressed: () => setState(() => _hidden = !_hidden),
              )
            : null,
      ),
    );
  }
}
