import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/features/reminders/presentation/providers/reminders_provider.dart';
import 'package:rita_mobile/features/reminders/presentation/screens/reminders_list_screen.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';

class RoutineStatusCard extends ConsumerWidget {
  const RoutineStatusCard({
    super.key,
    required this.userId,
    required this.userName,
    required this.observedRoutines,
    required this.missedOrLateRoutines,
  });

  final int userId;
  final String userName;
  final List<String> observedRoutines;
  final List<String> missedOrLateRoutines;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final remindersAsync = ref.watch(remindersProvider(userId));

    return InkWell(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute<void>(
          builder: (context) => RemindersListScreen(
            userId: userId,
            userName: userName,
          ),
        ),
      ),
      borderRadius: BorderRadius.circular(AppSpacing.cardRadius),
      child: RitaCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.calendar_today_rounded, size: 20, color: AppColors.primary),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  'Estado de Rutinas',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const Spacer(),
                const Icon(Icons.chevron_right_rounded, color: AppColors.onSurfaceMuted),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            
            // 1. URGENT: Missed routines
            if (missedOrLateRoutines.isNotEmpty) ...[
              _buildSection(
                context,
                title: 'Para revisar',
                items: _sortMissed(missedOrLateRoutines),
                icon: Icons.error_outline_rounded,
                color: AppColors.warning,
                isAlert: true,
              ),
              const SizedBox(height: AppSpacing.lg),
            ],

            // 2. ACTIVE CONFIGURATION (Requirement)
            remindersAsync.when(
              data: (reminders) {
                final active = reminders.where((r) => r.isActive).toList();
                if (active.isEmpty) return const SizedBox.shrink();
                
                return _buildSection(
                  context,
                  title: 'Próximos avisos',
                  items: active.map((r) => '${r.title} (${r.timeOfDay})').toList(),
                  icon: Icons.notifications_active_outlined,
                  color: AppColors.primary,
                );
              },
              loading: () => const SizedBox.shrink(),
              error: (_, __) => const SizedBox.shrink(),
            ),

            if (observedRoutines.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.lg),
                _buildSection(
                  context,
                  title: 'Rutinas completadas',
                  items: observedRoutines,
                  icon: Icons.check_circle_outline_rounded,
                  color: AppColors.success,
                ),
            ],

            if (observedRoutines.isEmpty && missedOrLateRoutines.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.xs),
                child: Text(
                  'Pulsa para configurar nuevas rutinas y recordatorios.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppColors.onSurfaceMuted,
                        fontStyle: FontStyle.italic,
                      ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  /// Prioritize: medication > meal > checkin > hydration (Requirement 2)
  List<String> _sortMissed(List<String> items) {
    final list = List<String>.from(items);
    list.sort((a, b) {
      final scoreA = _getPriorityScore(a);
      final scoreB = _getPriorityScore(b);
      return scoreA.compareTo(scoreB);
    });
    return list;
  }

  int _getPriorityScore(String text) {
    final lower = text.toLowerCase();
    if (lower.contains('medicación')) return 1;
    if (lower.contains('comida') || lower.contains('ali')) return 2;
    if (lower.contains('bienestar') || lower.contains('check')) return 3;
    if (lower.contains('hidrata')) return 4;
    return 10;
  }

  Widget _buildSection(
    BuildContext context, {
    required String title,
    required List<String> items,
    required IconData icon,
    required Color color,
    bool isAlert = false,
  }) {
    const maxVisible = 4; // Requirement 1
    final visibleItems = items.take(maxVisible).toList();
    final remainingCount = items.length - maxVisible;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: AppColors.onSurfaceMuted,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.5,
              ),
        ),
        const SizedBox(height: AppSpacing.sm),
        ...visibleItems.map((item) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: Row(
                children: [
                  Icon(icon, size: 16, color: color),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      item,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: isAlert ? AppColors.onSurface : AppColors.onSurfaceMuted,
                            fontWeight: isAlert ? FontWeight.w500 : FontWeight.normal,
                          ),
                    ),
                  ),
                ],
              ),
            )),
        if (remainingCount > 0)
          Padding(
            padding: const EdgeInsets.only(left: 24),
            child: Text(
              '+$remainingCount más',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.onSurfaceMuted,
                    fontStyle: FontStyle.italic,
                  ),
            ),
          ),
      ],
    );
  }
}
