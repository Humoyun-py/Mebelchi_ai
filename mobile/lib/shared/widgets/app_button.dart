import 'package:flutter/material.dart';

/// Primary action button; while [loading] it shows a spinner and ignores taps (no double submit).
class AppButton extends StatelessWidget {
  const AppButton({super.key, required this.label, required this.onPressed, this.loading = false, this.outlined = false, this.icon});
  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final bool outlined;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final child = loading
        ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
        : Row(mainAxisSize: MainAxisSize.min, children: [
            if (icon != null) ...[Icon(icon, size: 20), const SizedBox(width: 8)],
            Flexible(child: Text(label, overflow: TextOverflow.ellipsis)),
          ]);
    final action = loading ? null : onPressed;
    return Semantics(
      button: true,
      label: label,
      child: outlined ? OutlinedButton(onPressed: action, child: child) : FilledButton(onPressed: action, child: child),
    );
  }
}
