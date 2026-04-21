import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/features/conversations/data/models/conversation_memory_read.dart';
import 'package:rita_mobile/features/conversations/presentation/providers/memories_provider.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';

/// Sección desplegable en el perfil del cuidador que muestra lo que RITA
/// recuerda sobre la persona. Agrupa memorias por tipo para facilitar la lectura.
class RitaMemoriesSection extends ConsumerStatefulWidget {
  const RitaMemoriesSection({required this.userId, super.key});

  final int userId;

  @override
  ConsumerState<RitaMemoriesSection> createState() => _RitaMemoriesSectionState();
}

class _RitaMemoriesSectionState extends ConsumerState<RitaMemoriesSection> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return RitaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          // Header siempre visible — al pulsar expande/colapsa
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: <Widget>[
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.secondary.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(
                      Icons.psychology_rounded,
                      color: AppColors.secondary,
                      size: 22,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          'Lo que sabe RITA',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w700,
                                color: AppColors.onSurface,
                              ),
                        ),
                        Text(
                          'Memorias del sistema conversacional',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: AppColors.onSurfaceMuted,
                              ),
                        ),
                      ],
                    ),
                  ),
                  Icon(
                    _expanded
                        ? Icons.keyboard_arrow_up_rounded
                        : Icons.keyboard_arrow_down_rounded,
                    color: AppColors.onSurfaceMuted,
                  ),
                ],
              ),
            ),
          ),

          // Contenido expandible
          if (_expanded) ...<Widget>[
            const SizedBox(height: AppSpacing.md),
            const Divider(color: AppColors.border, height: 1),
            const SizedBox(height: AppSpacing.md),
            _MemoriesContent(userId: widget.userId),
          ],
        ],
      ),
    );
  }
}

class _MemoriesContent extends ConsumerWidget {
  const _MemoriesContent({required this.userId});

  final int userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(memoriesProvider(userId));

    return state.when(
      loading: () => const Center(
        child: Padding(
          padding: EdgeInsets.all(AppSpacing.md),
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      error: (_, __) => Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Row(
          children: <Widget>[
            const Icon(Icons.info_outline, size: 16, color: AppColors.onSurfaceMuted),
            const SizedBox(width: 8),
            Text(
              'No se pudieron cargar las memorias',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppColors.onSurfaceMuted,
                  ),
            ),
          ],
        ),
      ),
      data: (memories) {
        if (memories.isEmpty) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
            child: Text(
              'RITA aún no ha guardado memorias para esta persona. '
              'Se irán acumulando con las conversaciones.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppColors.onSurfaceMuted,
                    fontStyle: FontStyle.italic,
                  ),
            ),
          );
        }

        // Agrupar por tipo
        final grouped = <String, List<ConversationMemoryRead>>{};
        for (final m in memories) {
          grouped.putIfAbsent(m.memoryType, () => <ConversationMemoryRead>[]).add(m);
        }

        // Orden de visualización
        const typeOrder = <String>[
          'person', 'health', 'preference', 'routine', 'emotional', 'life_event',
        ];
        final sortedTypes = grouped.keys.toList()
          ..sort((a, b) {
            final ai = typeOrder.indexOf(a);
            final bi = typeOrder.indexOf(b);
            return (ai == -1 ? 99 : ai).compareTo(bi == -1 ? 99 : bi);
          });

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: sortedTypes.map((type) {
            final items = grouped[type]!;
            return _MemoryGroup(
              typeLabel: _typeLabel(type),
              typeIcon: _typeIcon(type),
              memories: items,
            );
          }).toList(),
        );
      },
    );
  }

  String _typeLabel(String type) {
    switch (type) {
      case 'person': return 'Persona';
      case 'health': return 'Salud';
      case 'preference': return 'Preferencias';
      case 'routine': return 'Rutinas';
      case 'emotional': return 'Estado emocional';
      case 'life_event': return 'Eventos de vida';
      default: return type;
    }
  }

  IconData _typeIcon(String type) {
    switch (type) {
      case 'person': return Icons.person_outline_rounded;
      case 'health': return Icons.favorite_border_rounded;
      case 'preference': return Icons.star_outline_rounded;
      case 'routine': return Icons.schedule_rounded;
      case 'emotional': return Icons.mood_rounded;
      case 'life_event': return Icons.auto_stories_rounded;
      default: return Icons.label_outline_rounded;
    }
  }
}

class _MemoryGroup extends StatelessWidget {
  const _MemoryGroup({
    required this.typeLabel,
    required this.typeIcon,
    required this.memories,
  });

  final String typeLabel;
  final IconData typeIcon;
  final List<ConversationMemoryRead> memories;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(typeIcon, size: 14, color: AppColors.primary),
              const SizedBox(width: 6),
              Text(
                typeLabel.toUpperCase(),
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.8,
                    ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          ...memories.map(
            (m) => Padding(
              padding: const EdgeInsets.only(bottom: 6, left: 20),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Text('· ', style: TextStyle(color: AppColors.onSurfaceMuted)),
                  Expanded(
                    child: Text(
                      m.content,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppColors.onSurface,
                          ),
                    ),
                  ),
                  if (m.confidence == 'high')
                    const Padding(
                      padding: EdgeInsets.only(left: 4, top: 1),
                      child: Icon(
                        Icons.verified_rounded,
                        size: 12,
                        color: AppColors.success,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
