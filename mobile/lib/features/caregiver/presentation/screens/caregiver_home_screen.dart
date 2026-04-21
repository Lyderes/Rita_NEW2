import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/constants/routes.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/core/utils/date_utils.dart';
import 'package:rita_mobile/features/alerts/presentation/providers/alerts_provider.dart';
import 'package:rita_mobile/features/caregiver/presentation/providers/caregiver_context_provider.dart';
import 'package:rita_mobile/features/caregiver/presentation/widgets/caregiver_person_header.dart';
import 'package:rita_mobile/features/conversations/presentation/widgets/conversations_section.dart';
import 'package:rita_mobile/features/caregiver/presentation/widgets/routine_status_card.dart';
import 'package:rita_mobile/features/caregiver/presentation/widgets/wellness_score_card.dart';
import 'package:rita_mobile/features/users/data/models/user_detail_bundle.dart';
import 'package:rita_mobile/features/users/presentation/providers/user_detail_provider.dart';
import 'package:rita_mobile/features/users/presentation/providers/users_provider.dart';
import 'package:rita_mobile/shared/widgets/app_empty_state.dart';
import 'package:rita_mobile/shared/widgets/app_error_state.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';
import 'package:rita_mobile/shared/widgets/status_chip.dart';

class CaregiverHomeScreen extends ConsumerWidget {
  const CaregiverHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usersState = ref.watch(usersControllerProvider);
    final activeUser = ref.watch(caregiverActiveUserProvider);

    return AppScaffold(
      title: 'Inicio',
      actions: [
        IconButton(
          onPressed: () async {
            if (activeUser != null) {
              await ref.read(usersControllerProvider.notifier).load();
              await ref.read(userDetailProvider(activeUser.id).notifier).reload();
              await ref.read(alertsControllerProvider.notifier).load();
            } else {
              await ref.read(usersControllerProvider.notifier).load();
            }
          },
          icon: const Icon(Icons.refresh_rounded),
          tooltip: 'Actualizar',
        ),
      ],
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: usersState.when(
          loading: () => const Center(child: AppLoader()),
          error: (error, _) => AppErrorState(
            message: 'No se pudo cargar la lista de personas monitorizadas.\n$error',
            onRetry: () => ref.read(usersControllerProvider.notifier).load(),
          ),
          data: (users) {
            if (users.isEmpty) {
              return const AppEmptyState(
                message: 'No hay personas monitorizadas para mostrar.',
              );
            }

            final user = activeUser ?? users.first;
            final detailState = ref.watch(userDetailProvider(user.id));

            return detailState.when(
              loading: () => const Center(child: AppLoader()),
              error: (error, _) => AppErrorState(
                message: extractUserDetailErrorMessage(error),
                onRetry: () => ref.read(userDetailProvider(user.id).notifier).reload(),
              ),
              data: (detail) => _HomeContent(
                detail: detail,
                pendingAlerts: _pendingAlerts(ref),
                onRefresh: () async {
                  await ref.read(usersControllerProvider.notifier).load();
                  await ref.read(userDetailProvider(user.id).notifier).reload();
                  await ref.read(alertsControllerProvider.notifier).load();
                },
              ),
            );
          },
        ),
      ),
    );
  }

  int _pendingAlerts(WidgetRef ref) {
    final alertsState = ref.watch(alertsControllerProvider);
    return alertsState.maybeWhen(
      data: (result) => result.items
          .where((alert) => alert.status.toLowerCase() == 'pending')
          .length,
      orElse: () => 0,
    );
  }
}

class _HomeContent extends ConsumerWidget {
  const _HomeContent({
    required this.detail,
    required this.pendingAlerts,
    required this.onRefresh,
  });

  final UserDetailBundle detail;
  final int pendingAlerts;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final statusTone = _statusTone(detail.status.currentStatus, pendingAlerts);

    // Compute weekly average from already-loaded daily scores
    final scores = detail.dailyScores;
    final daysWithData = scores.where((s) => s.globalScore > 0).toList();
    final weeklyAvg = daysWithData.isEmpty
        ? 0
        : (daysWithData.map((s) => s.globalScore).reduce((a, b) => a + b) /
                daysWithData.length)
            .round();

    // Most recent score with real data for narrative + routines
    final latestWithData = daysWithData.isNotEmpty ? daysWithData.first : null;

    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        children: <Widget>[
          CaregiverPersonHeader(
            user: detail.user,
            statusLabel: _humanCurrentStatus(detail.status.currentStatus),
            statusTone: statusTone,
          ),
          if (pendingAlerts > 0) ...[
            const SizedBox(height: AppSpacing.md),
            _PendingAlertsBanner(count: pendingAlerts),
          ],
          const SizedBox(height: AppSpacing.md),
          WellnessScoreCard(
            score: weeklyAvg,
            stateLabel: _humanScoreState(_scoreStateFromValue(weeklyAvg)),
            summary: latestWithData?.narrativeSummary ??
                'Aún no hay actividad esta semana para generar una valoración.',
            interpretation: latestWithData?.interpretation,
            factors: latestWithData?.mainFactors ?? [],
            label: 'Media de bienestar semanal · ${daysWithData.length} ${daysWithData.length == 1 ? 'día' : 'días'} con datos',
          ),
          if (latestWithData != null) ...[
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xl),
              child: RoutineStatusCard(
                userId: detail.user.id,
                userName: detail.user.fullName,
                observedRoutines: latestWithData.observedRoutines,
                missedOrLateRoutines: latestWithData.missedOrLateRoutines,
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.xl),
          ConversationsSection(userId: detail.user.id),
          const SizedBox(height: AppSpacing.xl * 2),
        ],
      ),
    );
  }

  String _scoreStateFromValue(int score) {
    if (score >= 80) {
      return 'good';
    }
    if (score >= 55) {
      return 'attention';
    }
    return 'review';
  }

  StatusTone _statusTone(String currentStatus, int pendingAlerts) {
    final status = currentStatus.toLowerCase();
    if (pendingAlerts > 0 || status.contains('incident') || status.contains('critical')) {
      return StatusTone.warning;
    }
    if (status.contains('offline')) {
      return StatusTone.critical;
    }
    return StatusTone.good;
  }

  String _humanCurrentStatus(String currentStatus) {
    final normalized = currentStatus.toLowerCase();
    if (normalized.contains('online')) {
      return 'En linea';
    }
    if (normalized.contains('offline')) {
      return 'Sin conexion';
    }
    if (normalized.contains('incident')) {
      return 'Con alerta activa';
    }
    return 'Monitoreo activo';
  }

  String _humanScoreState(String wellbeingState) {
    final state = wellbeingState.toLowerCase();
    if (state.contains('good') || state.contains('stable') || state.contains('bien')) {
      return 'Bien';
    }
    if (state.contains('attention') || state.contains('warning')) {
      return 'Atencion';
    }
    return 'Revisar';
  }

  String _naturalSummary({
    required UserDetailBundle detail,
    required int score,
    required int pendingAlerts,
  }) {
    final name = detail.user.fullName;
    final lastEventAt = detail.status.lastEventAt;
    final lastActivity = lastEventAt == null
        ? 'sin actividad registrada reciente'
        : 'ultima actividad ${AppDateUtils.toShortDateTime(lastEventAt)}';

    if (score >= 80 && pendingAlerts == 0) {
      return '$name se encuentra estable hoy, con $lastActivity.';
    }
    if (score >= 55) {
      return '$name requiere seguimiento preventivo; hay señales para revisar durante el dia.';
    }
    return '$name necesita atencion prioritaria. Revisa alertas y estado del dispositivo.';
  }
}

class _PendingAlertsBanner extends StatelessWidget {
  const _PendingAlertsBanner({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.of(context).pushNamed(AppRoutes.alerts),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.warningSoft,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: AppColors.warning.withValues(alpha: 0.2)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.white,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.warning.withValues(alpha: 0.1),
                    blurRadius: 10,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: const Icon(
                Icons.priority_high_rounded,
                color: AppColors.warning,
                size: 20,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '$count ${count == 1 ? 'alerta pendiente' : 'alertas pendientes'}',
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      color: AppColors.onSurface,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 2),
                  const Text(
                    'Revisa los detalles e indica si estás al tanto',
                    style: TextStyle(
                      color: AppColors.onSurfaceMuted,
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              color: AppColors.warning,
            ),
          ],
        ),
      ),
    );
  }
}
