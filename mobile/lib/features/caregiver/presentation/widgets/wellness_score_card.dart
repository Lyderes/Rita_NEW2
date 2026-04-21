import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';
import 'package:rita_mobile/shared/widgets/status_chip.dart';

class WellnessScoreCard extends StatelessWidget {
  const WellnessScoreCard({
    super.key,
    required this.score,
    required this.stateLabel,
    required this.summary,
    this.interpretation,
    this.factors = const [],
    this.label = 'Puntuación de bienestar de hoy',
  });

  final int score;
  final String stateLabel;
  final String summary;
  final String? interpretation;
  final List<String> factors;
  final String label;

  @override
  Widget build(BuildContext context) {
    final tone = _toneFromScore(score);
    final ringColor = _ringColor(tone);

    return RitaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: <Widget>[
          _ScoreRing(score: score, color: ringColor, stateLabel: stateLabel),
          const SizedBox(height: AppSpacing.lg),
          Text(
            summary,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  height: 1.5,
                  fontWeight: FontWeight.w600,
                  color: AppColors.onSurface,
                  fontSize: 16,
                ),
          ),
          if (this.interpretation != null && this.interpretation!.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              this.interpretation!,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    height: 1.4,
                    color: AppColors.onSurfaceMuted,
                    fontStyle: FontStyle.italic,
                  ),
            ),
          ],
          if (factors.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 8,
              runSpacing: 8,
              children: factors
                  .map((f) => Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: AppColors.surfaceVariant.withValues(alpha: 0.5),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppColors.border.withValues(alpha: 0.3)),
                        ),
                        child: Text(
                          f,
                          style: Theme.of(context)
                              .textTheme
                              .labelSmall
                              ?.copyWith(
                                color: AppColors.onSurface,
                                fontWeight: FontWeight.w600,
                              ),
                        ),
                      ))
                  .toList(),
            ),
          ],
          const SizedBox(height: AppSpacing.lg),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: AppColors.onSurfaceMuted,
                  letterSpacing: 0.2,
                ),
          ),
        ],
      ),
    );
  }

  StatusTone _toneFromScore(int value) {
    if (value >= 80) {
      return StatusTone.good;
    }
    if (value >= 55) {
      return StatusTone.warning;
    }
    return StatusTone.critical;
  }

  Color _ringColor(StatusTone tone) {
    switch (tone) {
      case StatusTone.good:
        return AppColors.success;
      case StatusTone.warning:
        return AppColors.warning;
      case StatusTone.critical:
        return AppColors.critical;
      case StatusTone.neutral:
        return AppColors.secondary;
    }
  }
}

class _ScoreRing extends StatelessWidget {
  const _ScoreRing({
    required this.score,
    required this.color,
    required this.stateLabel,
  });

  final int score;
  final Color color;
  final String stateLabel;

  @override
  Widget build(BuildContext context) {
    final normalized = (score.clamp(0, 100)) / 100;

    return SizedBox(
      width: 160,
      height: 160,
      child: Stack(
        alignment: Alignment.center,
        children: <Widget>[
          Container(
            width: 154,
            height: 154,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: color.withValues(alpha: 0.15),
                  blurRadius: 30,
                  spreadRadius: 2,
                ),
              ],
            ),
          ),
          SizedBox(
            width: 154,
            height: 154,
            child: CircularProgressIndicator(
              value: normalized.toDouble(),
              strokeWidth: 12,
              strokeCap: StrokeCap.round,
              backgroundColor: AppColors.surfaceVariant.withValues(alpha: 0.6),
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(
                '$score',
                style: Theme.of(context).textTheme.displayMedium?.copyWith(
                      color: color,
                      fontWeight: FontWeight.w900,
                      fontSize: 54,
                      letterSpacing: -2,
                    ),
              ),
              const SizedBox(height: 2),
              Text(
                stateLabel.toUpperCase(),
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: color.withValues(alpha: 0.8),
                      fontWeight: FontWeight.w800,
                      letterSpacing: 2.0,
                      fontSize: 11,
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
