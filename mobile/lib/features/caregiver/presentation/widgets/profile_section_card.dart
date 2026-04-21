import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';

class ProfileSectionCard extends StatelessWidget {
  const ProfileSectionCard({
    super.key,
    required this.title,
    required this.icon,
    required this.rows,
  });

  final String title;
  final IconData icon;
  final List<({String label, String value})> rows;

  @override
  Widget build(BuildContext context) {
    return RitaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.secondary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  icon,
                  color: AppColors.secondary,
                  size: 22,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: AppColors.onSurface,
                    ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          ...rows.asMap().entries.map(
            (entry) {
              final row = entry.value;
              final isLast = entry.key == rows.length - 1;
              return Column(
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              row.label,
                              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                    color: AppColors.onSurfaceMuted,
                                    fontWeight: FontWeight.w600,
                                    letterSpacing: 0.2,
                                  ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              row.value,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: AppColors.onSurface,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  if (!isLast) ...[
                    const SizedBox(height: AppSpacing.md),
                    const Divider(
                      color: AppColors.border,
                      height: 1,
                    ),
                    const SizedBox(height: AppSpacing.md),
                  ],
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
