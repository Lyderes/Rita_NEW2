import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';

enum StatusTone {
  good,
  warning,
  critical,
  neutral,
}

class StatusChip extends StatelessWidget {
  const StatusChip({
    super.key,
    required this.label,
    required this.tone,
    this.leadingIcon,
  });

  final String label;
  final StatusTone tone;
  final IconData? leadingIcon;

  factory StatusChip.fromString({
    Key? key,
    required String label,
    required String status,
    IconData? leadingIcon,
  }) {
    final String normalized = status.trim().toLowerCase();
    StatusTone tone = StatusTone.neutral;

    if (<String>{'ok', 'estable', 'resolved', 'healthy', 'good'}.contains(normalized)) {
      tone = StatusTone.good;
    } else if (<String>{'warning', 'attention', 'pendiente', 'medium'}.contains(normalized)) {
      tone = StatusTone.warning;
    } else if (<String>{'critical', 'critico', 'high', 'urgent', 'error'}.contains(normalized)) {
      tone = StatusTone.critical;
    }

    return StatusChip(
      key: key,
      label: label,
      tone: tone,
      leadingIcon: leadingIcon,
    );
  }

  @override
  Widget build(BuildContext context) {
    final ({Color fg, Color bg}) colors = _resolveColors();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: colors.bg,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: colors.fg.withValues(alpha: 0.12)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          if (leadingIcon != null) ...<Widget>[
            Icon(leadingIcon, size: 15, color: colors.fg),
            const SizedBox(width: AppSpacing.xs),
          ],
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: colors.fg,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.2,
                ),
          ),
        ],
      ),
    );
  }

  ({Color fg, Color bg}) _resolveColors() {
    switch (tone) {
      case StatusTone.good:
        return (fg: AppColors.success, bg: AppColors.successSoft);
      case StatusTone.warning:
        return (fg: AppColors.warning, bg: AppColors.warningSoft);
      case StatusTone.critical:
        return (fg: AppColors.critical, bg: AppColors.criticalSoft);
      case StatusTone.neutral:
        return (fg: AppColors.neutral, bg: AppColors.neutralSoft);
    }
  }
}
