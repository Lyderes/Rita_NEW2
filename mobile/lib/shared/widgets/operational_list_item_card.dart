import 'package:flutter/material.dart';
import 'package:rita_mobile/shared/widgets/operational_badges.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';

class OperationalListItemCard extends StatelessWidget {
  const OperationalListItemCard({
    required this.title,
    required this.typeLabel,
    required this.severity,
    required this.status,
    required this.timestampText,
    this.onTap,
    super.key,
  });

  final String title;
  final String typeLabel;
  final String severity;
  final String status;
  final String timestampText;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final severityColor = OperationalBadges.severityStripeColor(severity);

    return RitaCard(
      onTap: onTap,
      padding: EdgeInsets.zero,
      child: IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              width: 6,
              decoration: BoxDecoration(
                color: severityColor.withValues(alpha: 0.8),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(AppSpacing.cardRadius),
                  bottomLeft: Radius.circular(AppSpacing.cardRadius),
                ),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w700,
                                  color: AppColors.onSurface,
                                ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        const Icon(
                          Icons.chevron_right_rounded,
                          color: AppColors.onSurfaceMuted,
                          size: 20,
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      typeLabel,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: AppColors.onSurfaceMuted,
                            fontWeight: FontWeight.w500,
                          ),
                    ),
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        OperationalBadges.severityChip(context, severity),
                        OperationalBadges.statusChip(context, status),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      timestampText,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: AppColors.onSurfaceMuted,
                            fontSize: 11,
                          ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}