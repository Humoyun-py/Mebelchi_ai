import 'package:flutter/material.dart';

import '../../../core/errors/app_exception.dart';

/// Shared submit logic for forms: runs [action], tracks loading, keeps the server's error for display and re-validates
/// the form so field errors from the server show under their fields.
mixin FormSubmit<T extends StatefulWidget> on State<T> {
  final formKey = GlobalKey<FormState>();
  bool busy = false;
  AppException? error;

  String? fieldError(String name) => error?.fieldError(name);

  /// Errors that belong to no visible field (e.g. wrong password on login, or a field this form does not show).
  String? generalError(Set<String> shownFields) {
    final e = error;
    if (e == null) return null;
    if (e.kind != AppErrorKind.validation) return null; // non-validation errors go through S.error()
    final hidden = e.fields.keys.where((k) => !shownFields.contains(k));
    if (hidden.isNotEmpty) return e.fields[hidden.first]!.first;
    if (e.fields.isEmpty && e.detail.isNotEmpty) return e.detail;
    return null;
  }

  Future<bool> submit(Future<void> Function() action) async {
    if (busy || !(formKey.currentState?.validate() ?? false)) return false;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
      if (mounted) setState(() => busy = false);
      return true;
    } catch (e) {
      if (!mounted) return false;
      setState(() {
        busy = false;
        error = AppException.from(e);
      });
      WidgetsBinding.instance.addPostFrameCallback((_) => formKey.currentState?.validate());
      return false;
    }
  }
}
