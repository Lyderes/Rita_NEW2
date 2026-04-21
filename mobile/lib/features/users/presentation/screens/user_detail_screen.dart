import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/core/utils/date_utils.dart';
import 'package:rita_mobile/features/users/data/models/user_detail_bundle.dart';
import 'package:rita_mobile/features/users/presentation/providers/user_detail_provider.dart';
import 'package:rita_mobile/features/users/presentation/screens/interpretation_settings_screen.dart';
import 'package:rita_mobile/features/reminders/presentation/screens/reminders_list_screen.dart';
import 'package:rita_mobile/core/constants/routes.dart';
import 'package:rita_mobile/features/conversations/presentation/widgets/rita_memories_section.dart';
import 'package:rita_mobile/shared/widgets/app_error_state.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';

class UserDetailScreen extends ConsumerWidget {
  const UserDetailScreen({required this.userId, super.key});

  final int userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(userDetailProvider(userId));

    return AppScaffold(
      title: 'Estado de la Persona',
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: state.when(
          loading: () => const Center(child: AppLoader()),
          error: (error, _) => AppErrorState(
            message: extractUserDetailErrorMessage(error),
            onRetry: () => ref.read(userDetailProvider(userId).notifier).reload(),
          ),
          data: (detail) => RefreshIndicator(
            onRefresh: () => ref.read(userDetailProvider(userId).notifier).reload(),
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                _HeaderCard(detail: detail),
                const SizedBox(height: AppSpacing.sm),
                _OverviewCard(detail: detail),
                const SizedBox(height: AppSpacing.sm),
                RitaMemoriesSection(userId: userId),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _translateStatus(String status) {
  switch (status.toLowerCase()) {
    case 'critical': return 'Necesita atención urgente';
    case 'warning': return 'Seguimiento recomendado';
    case 'stable': return 'Estado estable y tranquilo';
    case 'online': return 'En línea / Conectado';
    case 'offline': return 'Sin conexión actualmente';
    default: return status;
  }
}

String _translateEvent(String type) {
  switch (type.toLowerCase()) {
    case 'assistant_response': return 'RITA le ha respondido';
    case 'user_speech': return 'La persona ha hablado con RITA';
    case 'reminder_sent': return 'Recordatorio enviado';
    case 'reminder_confirmed': return 'Recordatorio confirmado';
    case 'fall': return 'Posible caída detectada';
    case 'no_motion': return 'Falta de movimiento detectada';
    case 'significant_deviation': return 'Pequeña desviación en la rutina';
    default: return type;
  }
}

class _HeaderCard extends StatelessWidget {
  const _HeaderCard({required this.detail});

  final UserDetailBundle detail;

  @override
  Widget build(BuildContext context) {
    return RitaCard(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              detail.user.fullName,
              style: Theme.of(context)
                  .textTheme
                  .headlineSmall
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: AppSpacing.xs),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                _FactChip(label: _translateStatus(detail.status.currentStatus)),
              ],
            ),
            if ((detail.user.notes ?? '').isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                detail.user.notes!,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Colors.black87,
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.md),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                OutlinedButton.icon(
                  onPressed: () => Navigator.pushNamed(
                    context,
                    AppRoutes.userBaseline,
                    arguments: detail.user.id,
                  ),
                  icon: const Icon(Icons.health_and_safety_outlined),
                  label: const Text('Perfil de salud'),
                ),
                OutlinedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => InterpretationSettingsScreen(userId: detail.user.id),
                    ),
                  ),
                  icon: const Icon(Icons.tune),
                  label: const Text('IA: Acompañamiento'),
                ),
                OutlinedButton.icon(
                  onPressed: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => RemindersListScreen(
                        userId: detail.user.id,
                        userName: detail.user.fullName,
                      ),
                    ),
                  ),
                  icon: const Icon(Icons.notifications_none_rounded),
                  label: const Text('Rutinas y Avisos'),
                ),
                OutlinedButton.icon(
                  onPressed: () => Navigator.pushNamed(
                    context,
                    AppRoutes.editPersona,
                    arguments: detail.user,
                  ),
                  icon: const Icon(Icons.edit_note_rounded),
                  label: const Text('Editar Perfil'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _OverviewCard extends StatelessWidget {
  const _OverviewCard({required this.detail});

  final UserDetailBundle detail;

  @override
  Widget build(BuildContext context) {
    final status = detail.overview.currentStatus.toLowerCase();
    final hasIncident = detail.overview.openIncident != null;
    final pendingAlerts = detail.overview.pendingAlerts;
    final lastEvent = detail.overview.lastEvent;

    final (statusColor, statusBg, statusIcon, statusText) = _resolveStatus(status, hasIncident, pendingAlerts);

    return RitaCard(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Resumen de hoy',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: AppSpacing.md),

            // ── Banner de estado global ───────────────────────────────
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: statusBg,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  Icon(statusIcon, color: statusColor, size: 22),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      statusText,
                      style: TextStyle(
                        color: statusColor,
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // ── Grid de indicadores 2×2 ───────────────────────────────
            Row(
              children: [
                Expanded(
                  child: _StatTile(
                    icon: Icons.notifications_outlined,
                    label: 'Avisos',
                    value: pendingAlerts == 0 ? 'Todo en orden' : '$pendingAlerts pendiente${pendingAlerts > 1 ? 's' : ''}',
                    color: pendingAlerts == 0 ? AppColors.success : AppColors.warning,
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: _StatTile(
                    icon: hasIncident ? Icons.warning_amber_rounded : Icons.check_circle_outline_rounded,
                    label: 'Incidente',
                    value: hasIncident
                        ? _translateIncident(detail.overview.openIncident!.incidentType)
                        : 'Sin incidentes',
                    color: hasIncident ? AppColors.critical : AppColors.success,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),

            // ── Última actividad ──────────────────────────────────────
            if (lastEvent != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: AppColors.surfaceVariant,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Icon(Icons.access_time_rounded, size: 16, color: AppColors.onSurfaceMuted),
                    const SizedBox(width: 8),
                    Expanded(
                      child: RichText(
                        text: TextSpan(
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.onSurfaceMuted),
                          children: [
                            const TextSpan(text: 'Última actividad  '),
                            TextSpan(
                              text: _translateEvent(lastEvent.eventType),
                              style: const TextStyle(
                                color: AppColors.onSurface,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            TextSpan(text: '  ·  ${AppDateUtils.toShortDateTime(lastEvent.createdAt)}'),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  (Color, Color, IconData, String) _resolveStatus(
    String status, bool hasIncident, int pendingAlerts,
  ) {
    if (hasIncident || status.contains('critical') || status.contains('incident')) {
      return (AppColors.critical, AppColors.criticalSoft, Icons.priority_high_rounded, 'Necesita atención ahora');
    }
    if (pendingAlerts > 0 || status.contains('warning')) {
      return (AppColors.warning, AppColors.warningSoft, Icons.info_outline_rounded, 'Seguimiento recomendado hoy');
    }
    if (status.contains('offline')) {
      return (AppColors.warning, AppColors.warningSoft, Icons.wifi_off_rounded, 'Dispositivo sin conexión');
    }
    if (status.contains('online') || status.contains('stable')) {
      return (AppColors.success, AppColors.successSoft, Icons.check_circle_outline_rounded, 'Todo bien hoy');
    }
    return (AppColors.onSurfaceMuted, AppColors.surfaceVariant, Icons.help_outline_rounded, 'Estado desconocido');
  }

  String _translateIncident(String type) {
    switch (type.toLowerCase()) {
      case 'device_connectivity': return 'Conectividad del dispositivo';
      case 'no_motion': return 'Sin movimiento detectado';
      case 'fall': return 'Posible caída';
      case 'significant_deviation': return 'Desviación de rutina';
      default: return type;
    }
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.18)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(height: 6),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: AppColors.onSurfaceMuted,
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppColors.onSurface,
                  fontWeight: FontWeight.w600,
                ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

class _FactChip extends StatelessWidget {
  const _FactChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(label),
    );
  }
}
