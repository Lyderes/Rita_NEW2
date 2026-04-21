import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';

class AlertsHeader extends StatelessWidget {
  const AlertsHeader({
    super.key,
    required this.total,
    required this.critical,
    required this.pending,
  });

  final int total;
  final int critical;
  final int pending;

  @override
  Widget build(BuildContext context) {
    final hasCritical = critical > 0;
    final hasPending = pending > 0;

    if (hasCritical) {
      return _StatusBanner(
        icon: Icons.priority_high_rounded,
        color: AppColors.critical,
        gradient: AppColors.criticalGradient,
        headline: '$critical ${critical == 1 ? 'alerta urgente' : 'alertas urgentes'}',
        subtext: 'Requieren atención inmediata',
        total: total,
        pending: pending,
      );
    }

    if (hasPending) {
      return _StatusBanner(
        icon: Icons.notifications_active_rounded,
        color: AppColors.warning,
        gradient: AppColors.accentGradient,
        headline: '$pending ${pending == 1 ? 'alerta pendiente' : 'alertas pendientes'}',
        subtext: 'Revísalas cuando puedas',
        total: total,
        pending: pending,
      );
    }

    return _AllClearBanner(total: total);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Gradient banner for pending/critical state
// ─────────────────────────────────────────────────────────────────────────────
class _StatusBanner extends StatelessWidget {
  const _StatusBanner({
    required this.icon,
    required this.color,
    required this.gradient,
    required this.headline,
    required this.subtext,
    required this.total,
    required this.pending,
  });

  final IconData icon;
  final Color color;
  final LinearGradient gradient;
  final String headline;
  final String subtext;
  final int total;
  final int pending;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Container(
        decoration: BoxDecoration(
          gradient: gradient,
          borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.25),
              blurRadius: 16,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: Colors.white, size: 22),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    headline,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                      fontSize: 15,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtext,
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.85),
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            _MiniStat(label: 'Total', value: '$total', light: true),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// All-clear state — clean card
// ─────────────────────────────────────────────────────────────────────────────
class _AllClearBanner extends StatelessWidget {
  const _AllClearBanner({required this.total});

  final int total;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: RitaCard(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.success.withValues(alpha: 0.10),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.check_circle_outline_rounded,
                color: AppColors.success,
                size: 20,
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Todo al dia',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w700,
                          color: AppColors.onSurface,
                        ),
                  ),
                  Text(
                    'No hay alertas pendientes',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: AppColors.onSurfaceMuted,
                        ),
                  ),
                ],
              ),
            ),
            _MiniStat(label: 'Historial', value: '$total', light: false),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Compact stat chip
// ─────────────────────────────────────────────────────────────────────────────
class _MiniStat extends StatelessWidget {
  const _MiniStat({
    required this.label,
    required this.value,
    required this.light,
  });

  final String label;
  final String value;
  final bool light;

  @override
  Widget build(BuildContext context) {
    final textColor = light ? Colors.white : AppColors.onSurface;
    final mutedColor = light
        ? Colors.white.withValues(alpha: 0.75)
        : AppColors.onSurfaceMuted;
    final bgColor = light
        ? Colors.white.withValues(alpha: 0.15)
        : AppColors.surfaceVariant;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            value,
            style: TextStyle(
              color: textColor,
              fontWeight: FontWeight.w800,
              fontSize: 18,
            ),
          ),
          Text(
            label,
            style: TextStyle(
              color: mutedColor,
              fontSize: 11,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
