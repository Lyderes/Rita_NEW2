import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/core/utils/date_utils.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';
import 'package:rita_mobile/features/alerts/presentation/providers/alerts_providers.dart';
import 'package:rita_mobile/shared/widgets/app_error_state.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';

class AlertDetailScreen extends ConsumerStatefulWidget {
  const AlertDetailScreen({required this.alertId, super.key});

  final int alertId;

  @override
  ConsumerState<AlertDetailScreen> createState() => _AlertDetailScreenState();
}

class _AlertDetailScreenState extends ConsumerState<AlertDetailScreen> {
  @override
  Widget build(BuildContext context) {
    ref.listen<AsyncValue<void>>(acknowledgeAlertProvider(widget.alertId),
        (previous, next) {
      next.whenOrNull(
        error: (error, _) {
          ScaffoldMessenger.of(context)
            ..hideCurrentSnackBar()
            ..showSnackBar(
              SnackBar(content: Text(extractAlertErrorMessage(error))),
            );
        },
      );
    });

    ref.listen<AsyncValue<void>>(resolveAlertProvider(widget.alertId),
        (previous, next) {
      next.whenOrNull(
        error: (error, _) {
          ScaffoldMessenger.of(context)
            ..hideCurrentSnackBar()
            ..showSnackBar(
              SnackBar(content: Text(extractAlertErrorMessage(error))),
            );
        },
      );
    });

    final detailState = ref.watch(alertDetailFamilyProvider(widget.alertId));
    final acknowledgeState = ref.watch(acknowledgeAlertProvider(widget.alertId));
    final resolveState = ref.watch(resolveAlertProvider(widget.alertId));
    final isActionLoading =
        acknowledgeState.isLoading || resolveState.isLoading;

    return AppScaffold(
      title: 'Detalle de alerta',
      body: detailState.when(
        loading: () => const Center(child: AppLoader()),
        error: (error, _) => Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: AppErrorState(
            message: extractAlertErrorMessage(error),
            onRetry: () =>
                ref.read(alertDetailProvider(widget.alertId).notifier).load(),
          ),
        ),
        data: (alert) => _AlertDetailBody(
          alert: alert,
          isActionLoading: isActionLoading,
          onRefresh: () =>
              ref.read(alertDetailProvider(widget.alertId).notifier).load(),
          onAcknowledge: () => ref
              .read(acknowledgeAlertProvider(widget.alertId).notifier)
              .acknowledge(),
          onResolve: () =>
              ref.read(resolveAlertProvider(widget.alertId).notifier).resolve(),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Body
// ─────────────────────────────────────────────────────────────────────────────
class _AlertDetailBody extends StatelessWidget {
  const _AlertDetailBody({
    required this.alert,
    required this.isActionLoading,
    required this.onRefresh,
    required this.onAcknowledge,
    required this.onResolve,
  });

  final AlertRead alert;
  final bool isActionLoading;
  final VoidCallback onRefresh;
  final VoidCallback onAcknowledge;
  final VoidCallback onResolve;

  bool get _isPending =>
      ['pending', 'new'].contains(alert.status.toLowerCase());
  bool get _isAcknowledged => alert.status.toLowerCase() == 'acknowledged';
  bool get _isResolved => alert.status.toLowerCase() == 'resolved';

  @override
  Widget build(BuildContext context) {
    final color = _severityColor(alert.severity);

    return RefreshIndicator(
      onRefresh: () async => onRefresh(),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.md,
          AppSpacing.md,
          AppSpacing.xl,
        ),
        children: [
          // ── Hero ──────────────────────────────────────────────────────────
          _HeroCard(alert: alert, color: color),
          const SizedBox(height: AppSpacing.md),

          // ── Estado ────────────────────────────────────────────────────────
          _StatusCard(alert: alert),
          const SizedBox(height: AppSpacing.md),

          // ── Qué pasó ──────────────────────────────────────────────────────
          _WhatHappenedCard(alert: alert),
          const SizedBox(height: AppSpacing.md),

          // ── Timeline ──────────────────────────────────────────────────────
          _TimelineCard(alert: alert),
          const SizedBox(height: AppSpacing.lg),

          // ── Acciones ──────────────────────────────────────────────────────
          if (!_isResolved)
            _ActionsCard(
              alert: alert,
              isLoading: isActionLoading,
              canAcknowledge: _isPending,
              canResolve: _isAcknowledged || _isPending,
              onAcknowledge: onAcknowledge,
              onResolve: onResolve,
            ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Hero card — icono grande + título + descripción
// ─────────────────────────────────────────────────────────────────────────────
class _HeroCard extends StatelessWidget {
  const _HeroCard({required this.alert, required this.color});

  final AlertRead alert;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
        border: Border(left: BorderSide(color: color, width: 5)),
        boxShadow: const [
          BoxShadow(
            color: AppColors.shadowSoft,
            blurRadius: 8,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(_alertIcon(alert.alertType), color: color, size: 28),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _alertTitle(alert.alertType),
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: AppColors.onSurface,
                          height: 1.2,
                        ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _alertDescription(alert.alertType),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppColors.onSurfaceMuted,
                          height: 1.5,
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
}

// ─────────────────────────────────────────────────────────────────────────────
// Estado card
// ─────────────────────────────────────────────────────────────────────────────
class _StatusCard extends StatelessWidget {
  const _StatusCard({required this.alert});

  final AlertRead alert;

  @override
  Widget build(BuildContext context) {
    final (label, color, bg, icon) = _resolveStatus(alert.status);
    final (sevLabel, sevColor, sevBg) = _resolveSeverity(alert.severity);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          // Estado
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Estado',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: AppColors.onSurfaceMuted,
                        fontWeight: FontWeight.w600,
                      ),
                ),
                const SizedBox(height: 6),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: bg,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(icon, size: 14, color: color),
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
                ),
              ],
            ),
          ),
          // Severidad
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Prioridad',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: AppColors.onSurfaceMuted,
                        fontWeight: FontWeight.w600,
                      ),
                ),
                const SizedBox(height: 6),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: sevBg,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: sevColor,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 5),
                      Text(
                        sevLabel,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              color: sevColor,
                              fontWeight: FontWeight.w700,
                            ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  (String, Color, Color, IconData) _resolveStatus(String status) {
    switch (status.toLowerCase()) {
      case 'pending':
      case 'new':
        return ('Sin revisar', AppColors.warning, AppColors.warningSoft,
            Icons.schedule_rounded);
      case 'acknowledged':
        return ('Atendida', AppColors.primary, AppColors.primaryContainer,
            Icons.visibility_rounded);
      case 'resolved':
      case 'closed':
        return ('Resuelta', AppColors.success, AppColors.successSoft,
            Icons.check_circle_rounded);
      default:
        return (status, AppColors.neutral, AppColors.neutralSoft,
            Icons.info_rounded);
    }
  }

  (String, Color, Color) _resolveSeverity(String severity) {
    switch (severity.toLowerCase()) {
      case 'critical':
        return ('Critica', AppColors.critical,
            AppColors.critical.withValues(alpha: 0.10));
      case 'high':
        return ('Alta', const Color(0xFFE8773A),
            const Color(0xFFE8773A).withValues(alpha: 0.10));
      case 'medium':
      case 'warning':
        return ('Media', AppColors.warning, AppColors.warningSoft);
      case 'low':
      default:
        return ('Baja', AppColors.secondary,
            AppColors.secondary.withValues(alpha: 0.10));
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Qué pasó card — contexto humano
// ─────────────────────────────────────────────────────────────────────────────
class _WhatHappenedCard extends StatelessWidget {
  const _WhatHappenedCard({required this.alert});

  final AlertRead alert;

  @override
  Widget build(BuildContext context) {
    final explanation = _explanation(alert.alertType);
    final advice = _advice(alert.alertType);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.info_outline_rounded,
                  size: 18, color: AppColors.primary),
              const SizedBox(width: 8),
              Text(
                'Que ocurrio',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: AppColors.onSurface,
                    ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            explanation,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppColors.onSurfaceMuted,
                  height: 1.5,
                ),
          ),
          const SizedBox(height: AppSpacing.md),
          Container(
            padding: const EdgeInsets.all(AppSpacing.sm),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.07),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.lightbulb_outline_rounded,
                    size: 16, color: AppColors.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    advice,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w600,
                          height: 1.4,
                        ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _explanation(String type) {
    switch (type.toLowerCase().trim()) {
      case 'fall':
      case 'fall_detected':
      case 'possible_fall':
        return 'El sensor detectó un movimiento brusco o repentino que podría indicar una caida. El sistema lo registró automaticamente.';
      case 'no_motion':
      case 'inactivity':
        return 'No se detectó ningún movimiento durante un periodo más largo de lo habitual. Esto puede indicar que la persona lleva tiempo sin moverse.';
      case 'high_heart_rate':
      case 'heart_rate':
        return 'Las pulsaciones registradas superaron el umbral habitual para esta persona. Puede deberse a un esfuerzo fisico o a una situacion de estrés.';
      case 'device_connectivity':
      case 'heartbeat':
      case 'sensor_offline':
      case 'device_offline':
        return 'El sensor dejó de enviar señal al sistema. Esto puede deberse a falta de bateria, corte de internet o al sensor apagado.';
      case 'assistance_needed':
      case 'sos':
      case 'help_request':
        return 'La persona pulsó el botón de emergencia o solicitó ayuda a RITA. Esta alerta requiere atención inmediata.';
      case 'checkin_missed':
      case 'missed_checkin':
      case 'wellbeing_check_failed':
        return 'La persona no realizó su check-in diario en el tiempo esperado. Puede que esté ocupada, o puede necesitar asistencia.';
      case 'medication_missed':
      case 'medication':
        return 'No se confirmó la toma de medicacion del dia. La persona puede haber olvidado tomarla o no haber confirmado en la app.';
      case 'low_battery':
        return 'El nivel de bateria del sensor es muy bajo. Si no se recarga pronto, el sensor podría apagarse y dejar de monitorizar.';
      case 'emergency':
      case 'emergency_risk':
      case 'emergency_keyword_detected':
        return 'El sistema detectó una posible situacion de emergencia. Se recomienda actuar de inmediato y contactar con la persona o los servicios de emergencia.';
      default:
        return 'RITA detectó una situacion que requiere tu revision. Consulta los detalles y contacta con la persona si es necesario.';
    }
  }

  String _advice(String type) {
    switch (type.toLowerCase().trim()) {
      case 'fall':
      case 'fall_detected':
      case 'possible_fall':
        return 'Llama o envía un mensaje para confirmar que la persona se encuentra bien.';
      case 'no_motion':
      case 'inactivity':
        return 'Intenta contactar con la persona. Si no responde, considera visitar o avisar a alguien cercano.';
      case 'high_heart_rate':
      case 'heart_rate':
        return 'Pregunta si la persona se encuentra bien y si tuvo alguna actividad fisica reciente.';
      case 'device_connectivity':
      case 'heartbeat':
      case 'sensor_offline':
      case 'device_offline':
        return 'Pide a la persona que compruebe que el sensor está encendido y conectado a internet.';
      case 'assistance_needed':
      case 'sos':
      case 'help_request':
        return 'Contacta con la persona ahora mismo. Si no responde, llama a los servicios de emergencia.';
      case 'checkin_missed':
      case 'missed_checkin':
      case 'wellbeing_check_failed':
        return 'Envía un mensaje para saber cómo está. Si no responde en un tiempo razonable, llámala.';
      case 'medication_missed':
      case 'medication':
        return 'Recuérdale que tome su medicacion o verifica si necesita ayuda para hacerlo.';
      case 'low_battery':
        return 'Recuérdale que cargue el sensor o enchufe el cargador lo antes posible.';
      default:
        return 'Revisa la situacion y contacta con la persona si tienes dudas.';
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Timeline card — ciclo de vida real de la alerta
// ─────────────────────────────────────────────────────────────────────────────
class _TimelineCard extends StatelessWidget {
  const _TimelineCard({required this.alert});

  final AlertRead alert;

  bool get _isAcknowledged =>
      ['acknowledged', 'resolved', 'closed'].contains(alert.status.toLowerCase());
  bool get _isResolved =>
      ['resolved', 'closed'].contains(alert.status.toLowerCase());

  @override
  Widget build(BuildContext context) {
    final steps = <_TimelineStep>[
      _TimelineStep(
        icon: Icons.notifications_active_rounded,
        title: 'Alerta generada',
        subtitle: AppDateUtils.toShortDateTime(alert.createdAt),
        detail: _elapsed(alert.createdAt),
        state: _StepState.done,
      ),
      _TimelineStep(
        icon: Icons.send_rounded,
        title: 'Notificacion enviada',
        subtitle: alert.sentAt != null
            ? AppDateUtils.toShortDateTime(alert.sentAt!)
            : null,
        detail: alert.sentAt != null ? null : 'Pendiente de envio',
        state: alert.sentAt != null ? _StepState.done : _StepState.pending,
      ),
      _TimelineStep(
        icon: Icons.visibility_rounded,
        title: 'Atendida por el cuidador',
        subtitle: null,
        detail: _isAcknowledged ? 'Confirmada' : 'Sin confirmar aun',
        state: _isAcknowledged ? _StepState.done : _StepState.pending,
      ),
      _TimelineStep(
        icon: Icons.task_alt_rounded,
        title: 'Resuelta',
        subtitle: null,
        detail: _isResolved ? 'Cerrada' : 'Pendiente de resolucion',
        state: _isResolved ? _StepState.done : _StepState.pending,
      ),
    ];

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.timeline_rounded,
                  size: 18, color: AppColors.onSurfaceMuted),
              const SizedBox(width: 8),
              Text(
                'Seguimiento',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: AppColors.onSurface,
                    ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          ...List.generate(steps.length, (i) {
            final step = steps[i];
            final isLast = i == steps.length - 1;
            return _TimelineStepRow(
              step: step,
              isLast: isLast,
            );
          }),
        ],
      ),
    );
  }

  String _elapsed(DateTime createdAt) {
    final delta = DateTime.now().difference(createdAt);
    if (delta.inMinutes < 1) return 'Hace un momento';
    if (delta.inHours < 1) return 'Hace ${delta.inMinutes} min';
    if (delta.inDays < 1) return 'Hace ${delta.inHours} h';
    if (delta.inDays == 1) return 'Ayer';
    return 'Hace ${delta.inDays} dias';
  }
}

enum _StepState { done, pending }

class _TimelineStep {
  const _TimelineStep({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.detail,
    required this.state,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final String? detail;
  final _StepState state;
}

class _TimelineStepRow extends StatelessWidget {
  const _TimelineStepRow({required this.step, required this.isLast});

  final _TimelineStep step;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    final isDone = step.state == _StepState.done;
    final dotColor = isDone ? AppColors.success : AppColors.border;
    final iconColor = isDone ? AppColors.success : AppColors.onSurfaceMuted.withValues(alpha: 0.4);
    final titleColor = isDone ? AppColors.onSurface : AppColors.onSurfaceMuted;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Line + dot column ──────────────────────────────────────────────
          SizedBox(
            width: 32,
            child: Column(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: isDone
                        ? AppColors.success.withValues(alpha: 0.12)
                        : AppColors.border.withValues(alpha: 0.3),
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: dotColor,
                      width: isDone ? 1.5 : 1,
                    ),
                  ),
                  child: Icon(step.icon, size: 14, color: iconColor),
                ),
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 1.5,
                      margin: const EdgeInsets.symmetric(vertical: 3),
                      color: AppColors.border,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          // ── Text column ───────────────────────────────────────────────────
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    step.title,
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                          color: titleColor,
                        ),
                  ),
                  if (step.subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      step.subtitle!,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: AppColors.onSurface,
                            fontWeight: FontWeight.w500,
                          ),
                    ),
                  ],
                  if (step.detail != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      step.detail!,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: AppColors.onSurfaceMuted,
                          ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          // ── Badge ─────────────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.only(top: 5),
            child: isDone
                ? Icon(Icons.check_circle_rounded,
                    size: 16, color: AppColors.success)
                : Icon(Icons.radio_button_unchecked_rounded,
                    size: 16,
                    color: AppColors.onSurfaceMuted.withValues(alpha: 0.3)),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Actions card
// ─────────────────────────────────────────────────────────────────────────────
class _ActionsCard extends StatelessWidget {
  const _ActionsCard({
    required this.alert,
    required this.isLoading,
    required this.canAcknowledge,
    required this.canResolve,
    required this.onAcknowledge,
    required this.onResolve,
  });

  final AlertRead alert;
  final bool isLoading;
  final bool canAcknowledge;
  final bool canResolve;
  final VoidCallback onAcknowledge;
  final VoidCallback onResolve;

  @override
  Widget build(BuildContext context) {
    final severityColor = _severityColor(alert.severity);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(Icons.touch_app_rounded, size: 18, color: AppColors.onSurface),
              const SizedBox(width: 8),
              Text(
                'Que puedes hacer',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: AppColors.onSurface,
                    ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          if (canAcknowledge) ...[
            FilledButton.icon(
              onPressed: isLoading ? null : onAcknowledge,
              icon: isLoading
                  ? const SizedBox(
                      width: 18, height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.visibility_rounded, size: 20),
              label: const Text(
                'Estoy al tanto',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
              style: FilledButton.styleFrom(
                backgroundColor: severityColor,
                minimumSize: const Size.fromHeight(50),
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
          ],
          if (canResolve)
            OutlinedButton.icon(
              onPressed: isLoading ? null : onResolve,
              icon: const Icon(Icons.task_alt_rounded, size: 20),
              label: const Text(
                'Marcar como resuelta',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(50),
                foregroundColor: AppColors.success,
                side: BorderSide(color: AppColors.success),
              ),
            ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers compartidos
// ─────────────────────────────────────────────────────────────────────────────
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
