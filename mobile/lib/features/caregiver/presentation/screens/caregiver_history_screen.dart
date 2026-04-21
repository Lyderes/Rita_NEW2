import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/features/caregiver/presentation/providers/caregiver_context_provider.dart';
import 'package:rita_mobile/features/caregiver/presentation/widgets/weekly_wellness_chart.dart';
import 'package:rita_mobile/features/users/data/models/daily_score.dart';
import 'package:rita_mobile/features/users/data/models/event_read.dart';
import 'package:rita_mobile/features/users/presentation/providers/user_detail_provider.dart';
import 'package:rita_mobile/features/users/presentation/providers/users_provider.dart';
import 'package:rita_mobile/shared/widgets/app_empty_state.dart';
import 'package:rita_mobile/shared/widgets/app_error_state.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';

class CaregiverHistoryScreen extends ConsumerWidget {
  const CaregiverHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usersState = ref.watch(usersControllerProvider);
    final activeUser = ref.watch(caregiverActiveUserProvider);

    return AppScaffold(
      title: 'Historial',
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: usersState.when(
          loading: () => const Center(child: AppLoader()),
          error: (error, _) => AppErrorState(
            message: 'No se pudo cargar historial.\n$error',
            onRetry: () => ref.read(usersControllerProvider.notifier).load(),
          ),
          data: (users) {
            if (users.isEmpty) {
              return const AppEmptyState(message: 'Sin personas monitorizadas.');
            }

            final user = activeUser ?? users.first;
            final detailState = ref.watch(userDetailProvider(user.id));

            return detailState.when(
              loading: () => const Center(child: AppLoader()),
              error: (error, _) => AppErrorState(
                message: extractUserDetailErrorMessage(error),
                onRetry: () => ref.read(userDetailProvider(user.id).notifier).reload(),
              ),
              data: (detail) {
                final userName = user.fullName ?? 'la persona';
                final points = _buildWeeklyPoints(
                  detail.timeline.events,
                  detail.dailyScores,
                  userName,
                );
                return RefreshIndicator(
                  onRefresh: () async => ref.read(userDetailProvider(user.id).notifier).reload(),
                  child: ListView(
                    padding: const EdgeInsets.only(bottom: AppSpacing.xl),
                    children: <Widget>[
                      WeeklyWellnessChart(points: points),
                    ],
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }

  List<WeeklyWellnessPoint> _buildWeeklyPoints(
    List<UserEventRead> events,
    List<DailyScore> scores,
    String userName,
  ) {
    final now = DateTime.now();
    final labels = <String>['L', 'M', 'X', 'J', 'V', 'S', 'D'];
    final points = <WeeklyWellnessPoint>[];

    for (int i = 6; i >= 0; i--) {
      final day = now.subtract(Duration(days: i));
      
      // Try to find real score for this day
      final dailyScore = scores.where((s) {
        return s.date.year == day.year &&
            s.date.month == day.month &&
            s.date.day == day.day;
      }).firstOrNull;

      final dayEvents = events.where((event) {
        return event.createdAt.year == day.year &&
            event.createdAt.month == day.month &&
            event.createdAt.day == day.day;
      }).toList();

      int cappedScore;
      String summary;
      IconData? statusIcon;
      bool hasSleepData = false;

      if (dailyScore != null) {
        // USE REAL BACKEND DATA
        cappedScore = dailyScore.globalScore;
        summary = dailyScore.narrativeSummary;
        
        // Map icon based on real score
        if (cappedScore >= 85) {
          statusIcon = Icons.check_circle_outline_rounded;
        } else if (cappedScore >= 55) {
          statusIcon = Icons.info_outline_rounded;
        } else {
          statusIcon = Icons.error_outline_rounded;
        }
        
        // If the summary mentions alert or emergency, use warning
        if (summary.toLowerCase().contains('alerta') || 
            summary.toLowerCase().contains('emergencia') || 
            summary.toLowerCase().contains('caída')) {
          statusIcon = Icons.warning_amber_rounded;
        }

        // Sleep detection fallback if not in narrative
        final hasTiredness = dayEvents.any((e) {
          final desc = e.humanDescription?.toLowerCase() ?? '';
          return desc.contains('cansancio') || desc.contains('fatiga');
        });
        hasSleepData = dayEvents.isNotEmpty && !hasTiredness;

      } else {
        // NO BACKEND SCORE FOUND: Default to 0 instead of a guess (Phase 17.5)
        cappedScore = 0;
        summary = 'RITA no tiene suficientes datos sobre $userName hoy.';
        statusIcon = Icons.help_outline_rounded;
        hasSleepData = false;
      }

      points.add(
        WeeklyWellnessPoint(
          label: labels[day.weekday - 1],
          score: cappedScore,
          summary: summary,
          hasSleepData: hasSleepData,
          statusIcon: statusIcon,
          isToday: i == 0,
        ),
      );
    }

    return points;
  }
}
