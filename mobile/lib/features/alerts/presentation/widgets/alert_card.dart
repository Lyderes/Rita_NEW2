import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';

class AlertCard extends StatelessWidget {
  const AlertCard({
    required this.alert,
    this.onTap,
    this.onPrimaryAction,
    this.primaryActionLabel,
    this.onDelete,
    super.key,
  });

  final AlertRead alert;
  final VoidCallback? onTap;
  final VoidCallback? onPrimaryAction;
  final String? primaryActionLabel;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final color = _severityColor(alert.severity);
    final title = _alertTitle(alert.alertType);
    final description = _alertDescription(alert.alertType);
    final elapsed = _elapsedTime(alert.createdAt);
    final isPending = ['pending', 'new'].contains(alert.status.toLowerCase());

    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
          border: Border.all(color: AppColors.border),
          boxShadow: const [
            BoxShadow(
              color: AppColors.shadowSoft,
              blurRadius: 6,
              offset: Offset(0, 2),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Barra lateral de severidad
                Container(width: 5, color: color),
                // Contenido principal
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.md,
                      AppSpacing.md,
                      AppSpacing.md,
                      AppSpacing.md,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Cabecera: icono + título
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              padding: const EdgeInsets.all(9),
                              decoration: BoxDecoration(
                                color: color.withValues(alpha: 0.10),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Icon(
                                _alertIcon(alert.alertType),
                                color: color,
                                size: 20,
                              ),
                            ),
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    title,
                                    style: Theme.of(context)
                                        .textTheme
                                        .titleSmall
                                        ?.copyWith(
                                          fontWeight: FontWeight.w800,
                                          color: AppColors.onSurface,
                                          fontSize: 15,
                                          height: 1.2,
                                        ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    description,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall
                                        ?.copyWith(
                                          color: AppColors.onSurfaceMuted,
                                          height: 1.4,
                                        ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.sm),
                        // Fila inferior: estado + tiempo + borrar
                        Row(
                          children: [
                            _StatusBadge(status: alert.status),
                            const Spacer(),
                            Icon(
                              Icons.access_time_rounded,
                              size: 12,
                              color: AppColors.onSurfaceMuted,
                            ),
                            const SizedBox(width: 3),
                            Text(
                              elapsed,
                              style: Theme.of(context)
                                  .textTheme
                                  .labelSmall
                                  ?.copyWith(color: AppColors.onSurfaceMuted),
                            ),
                            if (onDelete != null) ...[
                              const SizedBox(width: AppSpacing.sm),
                              GestureDetector(
                                onTap: onDelete,
                                child: Container(
                                  padding: const EdgeInsets.all(6),
                                  decoration: BoxDecoration(
                                    color: Colors.red.shade50,
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Icon(
                                    Icons.delete_outline_rounded,
                                    size: 16,
                                    color: Colors.red.shade700,
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                        // Botón de acción si aplica
                        if (onPrimaryAction != null && isPending) ...[
                          const SizedBox(height: AppSpacing.sm),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton.icon(
                              onPressed: onPrimaryAction,
                              icon: const Icon(Icons.check_rounded, size: 18),
                              label: const Text(
                                'Estoy al tanto',
                                style: TextStyle(fontWeight: FontWeight.w800),
                              ),
                              style: FilledButton.styleFrom(
                                backgroundColor: color,
                                minimumSize: const Size.fromHeight(44),
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _alertTitle(String type) {
    switch (type.toLowerCase().trim()) {
      case 'fall':
      case 'fall_detected':
      case 'possible_fall':
        return 'Posible caida detectada';
      case 'no_motion':
      case 'inactivity':
        return 'Sin actividad detectada';
      case 'high_heart_rate':
      case 'heart_rate':
        return 'Pulsaciones elevadas';
      case 'significant_deviation':
      case 'deviation':
        return 'Cambio en la rutina';
      case 'device_connectivity':
      case 'heartbeat':
      case 'sensor_offline':
      case 'device_offline':
        return 'Sensor sin conexion';
      case 'assistance_needed':
      case 'sos':
      case 'help_request':
        return 'Solicitud de ayuda';
      case 'checkin_missed':
      case 'missed_checkin':
      case 'wellbeing_check_failed':
        return 'Check-in no realizado';
      case 'medication_missed':
      case 'medication':
        return 'Medicacion no confirmada';
      case 'low_battery':
        return 'Bateria baja en dispositivo';
      case 'emergency':
      case 'emergency_risk':
      case 'emergency_keyword_detected':
        return 'Posible emergencia';
      default:
        return 'Aviso del sistema';
    }
  }

  String _alertDescription(String type) {
    switch (type.toLowerCase().trim()) {
      case 'fall':
      case 'fall_detected':
      case 'possible_fall':
        return 'Se detecto un movimiento brusco. Comprueba que la persona esta bien.';
      case 'no_motion':
      case 'inactivity':
        return 'No se ha registrado actividad durante mas tiempo del habitual.';
      case 'high_heart_rate':
      case 'heart_rate':
        return 'Las pulsaciones registradas estan fuera del rango normal.';
      case 'significant_deviation':
      case 'deviation':
        return 'La rutina diaria ha cambiado de forma significativa hoy.';
      case 'device_connectivity':
      case 'heartbeat':
      case 'sensor_offline':
      case 'device_offline':
        return 'El sensor no responde. Comprueba que esta encendido y con bateria.';
      case 'assistance_needed':
      case 'sos':
      case 'help_request':
        return 'Se activo una peticion de ayuda. Contacta lo antes posible.';
      case 'checkin_missed':
      case 'missed_checkin':
      case 'wellbeing_check_failed':
        return 'La persona no ha realizado su check-in diario en el tiempo esperado.';
      case 'medication_missed':
      case 'medication':
        return 'No se ha confirmado la toma de medicacion del dia.';
      case 'low_battery':
        return 'El nivel de bateria del sensor es muy bajo. Recargalo pronto.';
      case 'emergency':
      case 'emergency_risk':
      case 'emergency_keyword_detected':
        return 'Se ha detectado una posible emergencia. Actua de inmediato.';
      default:
        return 'Revisa los detalles para mas informacion.';
    }
  }

  IconData _alertIcon(String type) {
    switch (type.toLowerCase().trim()) {
      case 'fall':
      case 'fall_detected':
      case 'possible_fall':
        return Icons.personal_injury_rounded;
      case 'no_motion':
      case 'inactivity':
        return Icons.directions_walk_rounded;
      case 'high_heart_rate':
      case 'heart_rate':
        return Icons.favorite_rounded;
      case 'significant_deviation':
      case 'deviation':
        return Icons.show_chart_rounded;
      case 'device_connectivity':
      case 'heartbeat':
      case 'sensor_offline':
      case 'device_offline':
        return Icons.wifi_off_rounded;
      case 'assistance_needed':
      case 'sos':
      case 'help_request':
        return Icons.sos_rounded;
      case 'checkin_missed':
      case 'missed_checkin':
      case 'wellbeing_check_failed':
        return Icons.event_busy_rounded;
      case 'medication_missed':
      case 'medication':
        return Icons.medication_rounded;
      case 'low_battery':
        return Icons.battery_alert_rounded;
      case 'emergency':
      case 'emergency_risk':
      case 'emergency_keyword_detected':
        return Icons.emergency_rounded;
      default:
        return Icons.notifications_rounded;
    }
  }

  Color _severityColor(String severity) {
    switch (severity.toLowerCase().trim()) {
      case 'critical':
        return AppColors.critical;
      case 'high':
        return const Color(0xFFE8773A);
      case 'warning':
      case 'medium':
        return AppColors.warning;
      case 'low':
      case 'info':
        return AppColors.secondary;
      default:
        return AppColors.neutral;
    }
  }

  String _elapsedTime(DateTime createdAt) {
    final delta = DateTime.now().difference(createdAt);
    if (delta.inMinutes < 1) return 'ahora mismo';
    if (delta.inHours < 1) return 'hace ${delta.inMinutes} min';
    if (delta.inDays < 1) return 'hace ${delta.inHours} h';
    if (delta.inDays == 1) return 'ayer';
    return 'hace ${delta.inDays} dias';
  }
}

// ----------------------------------------------------------------------------
// Badge de estado
// ----------------------------------------------------------------------------
class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final (label, color, bg) = _resolve(status);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 5),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }

  (String, Color, Color) _resolve(String status) {
    switch (status.toLowerCase().trim()) {
      case 'pending':
      case 'new':
        return ('Sin revisar', AppColors.warning, AppColors.warningSoft);
      case 'acknowledged':
        return ('Atendida', AppColors.primary, AppColors.primaryContainer);
      case 'resolved':
      case 'closed':
        return ('Resuelta', AppColors.success, AppColors.successSoft);
      default:
        return (status, AppColors.neutral, AppColors.neutralSoft);
    }
  }
}
