import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/core/utils/date_utils.dart';
import 'package:rita_mobile/features/caregiver/presentation/providers/caregiver_context_provider.dart';
import 'package:rita_mobile/features/caregiver/presentation/widgets/profile_section_card.dart';
import 'package:rita_mobile/features/users/data/models/event_read.dart';
import 'package:rita_mobile/features/users/presentation/providers/user_detail_provider.dart';
import 'package:rita_mobile/features/users/presentation/providers/users_provider.dart';
import 'package:rita_mobile/shared/widgets/app_empty_state.dart';
import 'package:rita_mobile/shared/widgets/app_error_state.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';

class CaregiverProfileScreen extends ConsumerWidget {
  const CaregiverProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final usersState = ref.watch(usersControllerProvider);
    final activeUser = ref.watch(caregiverActiveUserProvider);

    return AppScaffold(
      title: 'Perfil',
      body: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: usersState.when(
          loading: () => const Center(child: AppLoader()),
          error: (error, _) => AppErrorState(
            message: 'No se pudo cargar el perfil.\n$error',
            onRetry: () => ref.read(usersControllerProvider.notifier).load(),
          ),
          data: (users) {
            if (users.isEmpty) {
              return const AppEmptyState(message: 'Sin perfiles para mostrar.');
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
                final device = detail.overview.devices.isNotEmpty ? detail.overview.devices.first : null;

                return RefreshIndicator(
                  onRefresh: () => ref.read(userDetailProvider(user.id).notifier).reload(),
                  child: ListView(
                    padding: const EdgeInsets.only(bottom: AppSpacing.xl),
                    children: <Widget>[
                      ProfileSectionCard(
                        title: 'Perfil personal',
                        icon: Icons.person_rounded,
                        rows: <({String label, String value})>[
                          (label: 'Nombre', value: detail.user.fullName),
                          (label: 'Nacimiento', value: detail.user.birthDate == null ? '-' : AppDateUtils.toShortDate(detail.user.birthDate!)),
                          (label: 'Contexto', value: (detail.user.notes ?? '').isEmpty ? 'Sin notas registradas' : detail.user.notes!),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      ProfileSectionCard(
                        title: 'Dispositivo',
                        icon: Icons.router_rounded,
                        rows: <({String label, String value})>[
                          (label: 'Estado', value: device?.connectionStatus ?? 'Sin datos'),
                          (label: 'Nombre', value: device?.deviceName ?? 'No asignado'),
                          (label: 'Código', value: device?.deviceCode ?? '-'),
                          (label: 'Último latido', value: device?.lastSeenAt == null ? 'Sin registro' : AppDateUtils.toShortDateTime(device!.lastSeenAt!)),
                          (label: 'Información', value: 'Disponible en operaciones'),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      ProfileSectionCard(
                        title: 'Monitorización',
                        icon: Icons.monitor_heart_rounded,
                        rows: <({String label, String value})>[
                          (label: 'Check-in diario', value: _checkinState(detail.timeline.events)),
                          (label: 'Alerta (sin movimiento)', value: '45 minutos'),
                          (label: 'Crítica (sin movimiento)', value: '90 minutos'),
                          (label: 'Estado', value: 'Activo y funcionando'),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      const ProfileSectionCard(
                        title: 'Cuidadores vinculados',
                        icon: Icons.groups_rounded,
                        rows: <({String label, String value})>[
                          (label: 'Administrador', value: 'Cuenta actual'),
                          (label: 'Cuidadores', value: 'Preparado para múltiples'),
                          (label: 'Observadores', value: 'Permisos de lectura'),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      const ProfileSectionCard(
                        title: 'Privacidad y datos',
                        icon: Icons.privacy_tip_rounded,
                        rows: <({String label, String value})>[
                          (label: 'Consentimientos', value: 'Registrados y activos'),
                          (label: 'Almacenamiento', value: 'Datos en servidor seguro'),
                          (label: 'Control', value: 'Administrado por cuenta principal'),
                        ],
                      ),
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

  String _checkinState(List<UserEventRead> events) {
    final now = DateTime.now();
    final hasCheckinToday = events.any((event) {
      final normalized = event.eventType.toLowerCase();
      return normalized.contains('checkin') &&
          event.createdAt.year == now.year &&
          event.createdAt.month == now.month &&
          event.createdAt.day == now.day;
    });
    return hasCheckinToday ? 'Completado hoy' : 'Pendiente hoy';
  }
}
