import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/constants/routes.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';
import 'package:rita_mobile/features/alerts/presentation/providers/alerts_provider.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';
import 'package:rita_mobile/features/alerts/presentation/widgets/alert_card.dart';
import 'package:rita_mobile/features/alerts/presentation/widgets/alerts_header.dart';
import 'package:rita_mobile/shared/widgets/app_empty_state.dart';
import 'package:rita_mobile/shared/widgets/app_error_state.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';

class AlertsScreen extends ConsumerStatefulWidget {
  const AlertsScreen({super.key});

  @override
  ConsumerState<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends ConsumerState<AlertsScreen> {
  String? _severityFilter; // null = todas

  List<AlertRead> _applyFilter(List<AlertRead> alerts) {
    if (_severityFilter == null) return alerts;
    if (_severityFilter == 'urgent') {
      return alerts.where((a) => ['critical', 'high'].contains(a.severity.toLowerCase())).toList();
    }
    return alerts.where((a) => a.severity.toLowerCase() == _severityFilter).toList();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(alertsControllerProvider);

    return AppScaffold(
      title: 'Alertas',
      actions: [
        IconButton(
          onPressed: () => ref.read(alertsControllerProvider.notifier).load(),
          icon: const Icon(Icons.refresh_rounded),
          tooltip: 'Actualizar',
        ),
      ],
      body: state.when(
        loading: () => const Center(child: AppLoader()),
        error: (error, _) => Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: AppErrorState(
            message: error.toString(),
            onRetry: () => ref.read(alertsControllerProvider.notifier).load(),
          ),
        ),
        data: (result) {
          if (result.items.isEmpty) {
            return const Padding(
              padding: EdgeInsets.all(AppSpacing.md),
              child: AppEmptyState(message: 'Sin alertas disponibles'),
            );
          }

          final allPending = result.items
              .where((a) => ['pending', 'acknowledged', 'new'].contains(a.status.toLowerCase()))
              .toList();
          final allResolved = result.items
              .where((a) => ['resolved', 'closed'].contains(a.status.toLowerCase()))
              .toList();

          final pendingAlerts  = _applyFilter(allPending);
          final resolvedAlerts = _applyFilter(allResolved);

          final pending  = allPending.length;
          // Solo cuentan como urgentes las alertas pendientes con severidad crítica/alta
          final critical = allPending
              .where((a) => ['critical', 'high'].contains(a.severity.toLowerCase()))
              .length;

          return RefreshIndicator(
            onRefresh: () => ref.read(alertsControllerProvider.notifier).load(),
            child: ListView(
              padding: const EdgeInsets.only(top: AppSpacing.md, bottom: AppSpacing.xl),
              children: [
                AlertsHeader(
                  total: result.total,
                  pending: pending,
                  critical: critical,
                ),
                const SizedBox(height: AppSpacing.md),
                _FilterBar(
                  selected: _severityFilter,
                  onSelected: (val) => setState(() => _severityFilter = val),
                ),
                const SizedBox(height: AppSpacing.lg),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  child: Column(
                    children: [
                      _SectionHeader(
                        title: 'Pendientes',
                        subtitle: 'Requieren atención o seguimiento',
                        count: pendingAlerts.length,
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      if (pendingAlerts.isEmpty)
                        const _SectionEmpty(message: 'No hay alertas pendientes.')
                      else
                        ...pendingAlerts.map((alert) => Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.md),
                          child: AlertCard(
                            alert: alert,
                            onTap: () => Navigator.of(context).pushNamed(
                              AppRoutes.alertDetail,
                              arguments: alert.id,
                            ),
                            onPrimaryAction: _isPending(alert)
                                ? () => _acknowledge(context, ref, alert.id)
                                : null,
                            primaryActionLabel: _isPending(alert) ? 'Confirmar — Estoy al tanto' : null,
                          ),
                        )),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  child: Column(
                    children: [
                      _SectionHeader(
                        title: 'Resueltas',
                        subtitle: 'Cerradas o ya revisadas',
                        count: resolvedAlerts.length,
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      if (resolvedAlerts.isEmpty)
                        const _SectionEmpty(message: 'Aún no hay alertas resueltas.')
                      else
                        ...resolvedAlerts.map((alert) => Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.md),
                          child: AlertCard(
                            alert: alert,
                            onTap: () => Navigator.of(context).pushNamed(
                              AppRoutes.alertDetail,
                              arguments: alert.id,
                            ),
                            onDelete: () => _deleteAlert(context, ref, alert.id),
                          ),
                        )),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  bool _isPending(AlertRead alert) {
    final status = alert.status.toLowerCase();
    return status == 'pending' || status == 'new';
  }

  Future<void> _acknowledge(BuildContext context, WidgetRef ref, int alertId) async {
    try {
      await ref.read(alertsRepositoryProvider).acknowledgeAlert(alertId);
      await ref.read(alertsControllerProvider.notifier).load();
      if (context.mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(const SnackBar(content: Text('Alerta marcada como atendida.')));
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(const SnackBar(content: Text('No se pudo confirmar la alerta.')));
      }
    }
  }

  Future<void> _deleteAlert(BuildContext context, WidgetRef ref, int alertId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Eliminar alerta'),
        content: const Text(
          'Esta alerta se eliminara definitivamente. Esta accion no se puede deshacer.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red.shade700),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      await ref.read(alertsRepositoryProvider).deleteAlert(alertId);
      await ref.read(alertsControllerProvider.notifier).load();
      if (context.mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(const SnackBar(content: Text('Alerta eliminada.')));
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(const SnackBar(content: Text('No se pudo eliminar la alerta.')));
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

class _FilterBar extends StatelessWidget {
  const _FilterBar({required this.selected, required this.onSelected});

  final String? selected;
  final ValueChanged<String?> onSelected;

  static const _filters = [
    ('urgent', 'Urgente', Color(0xFFE53935)),
    ('medium', 'Media',   Color(0xFFFB8C00)),
    ('low',    'Baja',    Color(0xFF1E88E5)),
  ];

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Row(
        children: [
          _chip(
            label: 'Todas',
            color: AppColors.primary,
            isSelected: selected == null,
            onTap: () => onSelected(null),
          ),
          const SizedBox(width: 8),
          ..._filters.map((s) => Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _chip(
              label: s.$2,
              color: s.$3,
              isSelected: selected == s.$1,
              onTap: () => onSelected(selected == s.$1 ? null : s.$1),
            ),
          )),
        ],
      ),
    );
  }

  Widget _chip({
    required String label,
    required Color color,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: isSelected ? color : color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? color : color.withValues(alpha: 0.3),
            width: 1.2,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: isSelected ? Colors.white : color,
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Section helpers
// ---------------------------------------------------------------------------

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    required this.subtitle,
    required this.count,
  });

  final String title;
  final String subtitle;
  final int count;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: AppColors.onSurface,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: AppColors.onSurfaceMuted,
                    ),
              ),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: AppColors.secondary.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            '$count',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: AppColors.secondary,
                  fontWeight: FontWeight.w600,
                ),
          ),
        ),
      ],
    );
  }
}

class _SectionEmpty extends StatelessWidget {
  const _SectionEmpty({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg, horizontal: AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(
              Icons.check_circle_outline_rounded,
              size: 40,
              color: AppColors.success.withValues(alpha: 0.5),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              message,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppColors.onSurfaceMuted,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
