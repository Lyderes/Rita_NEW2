import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/core/utils/date_utils.dart';
import 'package:rita_mobile/features/caregiver/presentation/utils/activity_presenter.dart';
import 'package:rita_mobile/features/users/data/models/event_read.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/users/presentation/providers/users_provider.dart';
import 'package:rita_mobile/features/users/presentation/providers/user_detail_provider.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

class RecentActivityList extends ConsumerWidget {
  const RecentActivityList({
    super.key,
    required this.events,
    required this.onOpenDetail,
  });

  final List<UserEventRead> events;
  final ValueChanged<UserEventRead> onOpenDetail;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return RitaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Actividad reciente',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: AppSpacing.sm),
          if (events.isEmpty)
            Text(
              'Sin actividad reciente para mostrar.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: AppColors.onSurfaceMuted,
                  ),
            )
          else
            ...events
                .where((event) {
                  final type = event.eventType.toLowerCase();
                  // Hide technical noise
                  if (type.contains('heartbeat') ||
                      type.contains('connectivity') ||
                      type.contains('online') ||
                      type.contains('offline')) {
                    return false;
                  }
                  // Hide redundant wellness events already summarized in the Score Card
                  if (type.contains('checkin') || type.contains('wellbeing')) {
                    return false;
                  }
                  return true;
                })
                .take(5)
                .map(
                  (event) {
                    final display = ActivityPresenter.getDisplayModel(event);
                    return Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Container(
                          width: 44,
                          height: 44,
                          decoration: BoxDecoration(
                            color: _colorForEvent(event.eventType).withValues(alpha: 0.12),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            _iconForEvent(event.eventType),
                            color: _colorForEvent(event.eventType),
                            size: 20,
                          ),
                        ),
                        title: Text(
                          display.title,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                                fontSize: 14,
                                color: AppColors.onSurface,
                              ),
                        ),
                        subtitle: Text(
                          '${display.subtitle} • ${AppDateUtils.toShortDateTime(event.createdAt)}',
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                color: AppColors.onSurfaceMuted,
                                fontWeight: FontWeight.w500,
                              ),
                        ),
                        trailing: _buildTrailing(context, ref, event),
                        onTap: () => onOpenDetail(event),
                      ),
                    );
                  },
                ),
        ],
      ),
    );
  }

  Color _colorForEvent(String eventType) {
    final normalized = eventType.toLowerCase();
    if (normalized.contains('fall') || normalized.contains('critical')) {
      return AppColors.critical;
    }
    if (normalized.contains('motion')) {
      return AppColors.info;
    }
    if (normalized.contains('checkin') || normalized.contains('wellbeing')) {
      return AppColors.success;
    }
    return AppColors.secondary;
  }

  Widget _buildTrailing(BuildContext context, WidgetRef ref, UserEventRead event) {
    final payload = event.payloadJson;
    final isPending = event.eventType == 'reminder_triggered' && 
                     payload != null && 
                     payload['confirmation_status'] == 'pending';

    if (isPending) {
      return TextButton(
        onPressed: () async {
          try {
            // Using existing repository pattern if available, or direct api
            // For simplicity in this phase, I'll use a direct call if we can get the api
            // though usually it goes through a controller.
            // Let's assume we can trigger a reload after confirmation.
            final usersApi = ref.read(usersApiProvider);
            await usersApi.confirmReminder(event.id);
            
            // Refresh the whole user detail to see the change
            ref.read(userDetailProvider(event.userId).notifier).reload();
            
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Recordatorio confirmado')),
              );
            }
          } catch (e) {
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Error al confirmar: $e')),
              );
            }
          }
        },
        child: const Text('Confirmar'),
      );
    }

    return const Icon(Icons.chevron_right_rounded);
  }

  IconData _iconForEvent(String eventType) {
    final normalized = eventType.toLowerCase();
    if (normalized.contains('checkin')) {
      return Icons.fact_check_rounded;
    }
    if (normalized.contains('heartbeat') || normalized.contains('online')) {
      return Icons.favorite_rounded;
    }
    if (normalized.contains('motion')) {
      return Icons.directions_walk_rounded;
    }
    if (normalized.contains('fall')) {
      return Icons.personal_injury_rounded;
    }
    if (normalized.contains('user_speech')) {
      return Icons.record_voice_over_rounded;
    }
    if (normalized.contains('assistant_response')) {
      return Icons.smart_toy_rounded;
    }
    return Icons.bolt_rounded;
  }
}
