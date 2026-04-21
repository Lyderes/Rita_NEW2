import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';

class WeeklyWellnessPoint {
  WeeklyWellnessPoint({
    required this.label,
    required this.score,
    required this.summary,
    this.hasSleepData = false,
    this.statusIcon,
    this.isToday = false,
  });

  final String label;
  final int score;
  final String summary;
  final bool hasSleepData;
  final IconData? statusIcon;
  final bool isToday;

  bool get hasData => score > 0;
}

class WeeklyWellnessChart extends StatelessWidget {
  const WeeklyWellnessChart({super.key, required this.points});

  final List<WeeklyWellnessPoint> points;

  @override
  Widget build(BuildContext context) {
    final daysWithData = points.where((p) => p.hasData).toList();
    final avg = daysWithData.isEmpty
        ? 0
        : (daysWithData.map((p) => p.score).reduce((a, b) => a + b) / daysWithData.length).round();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        // ── Cabecera semanal ──────────────────────────────────────────
        _WeekSummaryHeader(average: avg, daysWithData: daysWithData.length),
        const SizedBox(height: AppSpacing.md),

        // ── Minigráfica de puntos ─────────────────────────────────────
        _SparkRow(points: points),
        const SizedBox(height: AppSpacing.lg),

        // ── Tarjetas de días ──────────────────────────────────────────
        ...points.reversed.map((p) => _DayCard(point: p)),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Cabecera con puntuación media
// ─────────────────────────────────────────────────────────────────────────────

class _WeekSummaryHeader extends StatelessWidget {
  const _WeekSummaryHeader({required this.average, required this.daysWithData});

  final int average;
  final int daysWithData;

  @override
  Widget build(BuildContext context) {
    final color = _scoreColor(average);
    final label = _scoreLabel(average);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[
            color.withValues(alpha: 0.12),
            color.withValues(alpha: 0.04),
          ],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.20)),
      ),
      child: Row(
        children: <Widget>[
          // Círculo de puntuación grande
          Container(
            width: 72,
            height: 72,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withValues(alpha: 0.12),
              border: Border.all(color: color.withValues(alpha: 0.35), width: 2),
            ),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(
                    daysWithData == 0 ? '—' : '$average',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      color: color,
                      height: 1,
                    ),
                  ),
                  if (daysWithData > 0)
                    Text(
                      'media',
                      style: TextStyle(
                        fontSize: 10,
                        color: color.withValues(alpha: 0.8),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Esta semana',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                        color: AppColors.onSurface,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  daysWithData == 0
                      ? 'Sin datos disponibles aún'
                      : '$label · $daysWithData ${daysWithData == 1 ? 'día' : 'días'} con datos',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppColors.onSurfaceMuted,
                      ),
                ),
                const SizedBox(height: 8),
                if (daysWithData > 0) _TrendBar(average: average, color: color),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TrendBar extends StatelessWidget {
  const _TrendBar({required this.average, required this.color});

  final int average;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(4),
      child: LinearProgressIndicator(
        value: average / 100,
        minHeight: 6,
        backgroundColor: color.withValues(alpha: 0.12),
        valueColor: AlwaysStoppedAnimation<Color>(color),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Mini sparkline de puntos con dots
// ─────────────────────────────────────────────────────────────────────────────

class _SparkRow extends StatelessWidget {
  const _SparkRow({required this.points});

  final List<WeeklyWellnessPoint> points;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 56,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: points.map((p) {
          final color = p.hasData ? _scoreColor(p.score) : AppColors.border;
          final barH = p.hasData ? (p.score / 100 * 40).clamp(4.0, 40.0) : 4.0;

          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 3),
              child: ClipRect(
               child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: <Widget>[
                  if (p.isToday)
                    Container(
                      width: 4,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: 3),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: AppColors.primary,
                      ),
                    ),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 400),
                    curve: Curves.easeOut,
                    height: barH,
                    decoration: BoxDecoration(
                      color: p.isToday ? AppColors.primary : color,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    p.label,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: p.isToday ? FontWeight.w800 : FontWeight.w500,
                      color: p.isToday ? AppColors.primary : AppColors.onSurfaceMuted,
                    ),
                  ),
                ],
               ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tarjeta de día individual
// ─────────────────────────────────────────────────────────────────────────────

class _DayCard extends StatelessWidget {
  const _DayCard({required this.point});

  final WeeklyWellnessPoint point;

  @override
  Widget build(BuildContext context) {
    final color = point.hasData ? _scoreColor(point.score) : AppColors.onSurfaceMuted;
    final bgColor = point.hasData ? color.withValues(alpha: 0.06) : Colors.transparent;

    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: point.isToday
              ? AppColors.primary.withValues(alpha: 0.40)
              : point.hasData
                  ? color.withValues(alpha: 0.15)
                  : AppColors.border,
          width: point.isToday ? 1.5 : 1,
        ),
      ),
      child: Row(
        children: <Widget>[
          // Badge de puntuación
          _ScoreBadge(score: point.score, hasData: point.hasData, isToday: point.isToday),
          const SizedBox(width: 14),

          // Contenido
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Text(
                      point.isToday ? 'Hoy' : _fullLabel(point.label),
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: point.isToday ? AppColors.primary : AppColors.onSurface,
                          ),
                    ),
                    if (point.isToday) ...<Widget>[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          'hoy',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            color: AppColors.primary,
                          ),
                        ),
                      ),
                    ],
                    if (point.hasSleepData) ...<Widget>[
                      const SizedBox(width: 6),
                      Icon(Icons.bedtime_outlined, size: 13, color: AppColors.primary),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  point.summary,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: point.hasData
                            ? AppColors.onSurface
                            : AppColors.onSurfaceMuted,
                        fontStyle: point.hasData ? FontStyle.normal : FontStyle.italic,
                      ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _fullLabel(String short) {
    switch (short) {
      case 'L': return 'Lunes';
      case 'M': return 'Martes';
      case 'X': return 'Miércoles';
      case 'J': return 'Jueves';
      case 'V': return 'Viernes';
      case 'S': return 'Sábado';
      case 'D': return 'Domingo';
      default: return short;
    }
  }
}

class _ScoreBadge extends StatelessWidget {
  const _ScoreBadge({
    required this.score,
    required this.hasData,
    required this.isToday,
  });

  final int score;
  final bool hasData;
  final bool isToday;

  @override
  Widget build(BuildContext context) {
    final color = isToday
        ? AppColors.primary
        : hasData
            ? _scoreColor(score)
            : AppColors.border;

    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color.withValues(alpha: hasData ? 0.12 : 0.5),
        border: Border.all(
          color: color.withValues(alpha: hasData ? 0.35 : 0.3),
          width: 1.5,
        ),
      ),
      child: Center(
        child: hasData
            ? Text(
                '$score',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: color,
                ),
              )
            : Icon(Icons.remove, size: 16, color: color),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers de color y etiqueta
// ─────────────────────────────────────────────────────────────────────────────

Color _scoreColor(int score) {
  if (score >= 80) return AppColors.success;
  if (score >= 55) return AppColors.warning;
  return AppColors.critical;
}

String _scoreLabel(int score) {
  if (score >= 80) return 'Buen estado';
  if (score >= 55) return 'Seguimiento recomendado';
  return 'Requiere atención';
}
