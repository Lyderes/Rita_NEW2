
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/features/users/data/models/user_baseline_profile.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';
import 'package:rita_mobile/shared/widgets/app_error_state.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';
import 'package:rita_mobile/shared/widgets/rita_card.dart';

// ── Provider ────────────────────────────────────────────────────────────────

final _baselineProvider = FutureProvider.family<UserBaselineProfile, int>(
  (ref, userId) => ref.read(baselineRepositoryProvider).getBaseline(userId),
);

// ── Screen ──────────────────────────────────────────────────────────────────

class BaselineProfileScreen extends ConsumerStatefulWidget {
  const BaselineProfileScreen({super.key, required this.userId});

  final int userId;

  @override
  ConsumerState<BaselineProfileScreen> createState() =>
      _BaselineProfileScreenState();
}

class _BaselineProfileScreenState
    extends ConsumerState<BaselineProfileScreen> {
  // form state
  String _mood = 'neutral';
  String _activityLevel = 'medium';
  String _energyLevel = 'medium';
  bool _livesAlone = true;
  int _mealsPerDay = 3;
  double _sleepHours = 8.0;
  String _socialLevel = 'medium';
  final _notesController = TextEditingController();

  bool _loaded = false;
  bool _saving = false;

  void _initFromProfile(UserBaselineProfile p) {
    if (_loaded) return;
    _loaded = true;
    _mood = p.usualMood;
    _activityLevel = p.usualActivityLevel;
    _energyLevel = p.usualEnergyLevel;
    _livesAlone = p.livesAlone;
    _mealsPerDay = p.mealsPerDay;
    _sleepHours = p.usualSleepHours;
    _socialLevel = p.socialInteractionLevel;
    _notesController.text = p.notes ?? '';
  }

  Future<void> _save(UserBaselineProfile current) async {
    setState(() => _saving = true);
    try {
      final updated = current.copyWith(
        usualMood: _mood,
        usualActivityLevel: _activityLevel,
        usualEnergyLevel: _energyLevel,
        livesAlone: _livesAlone,
        mealsPerDay: _mealsPerDay,
        usualSleepHours: _sleepHours,
        socialInteractionLevel: _socialLevel,
        notes: _notesController.text.trim().isEmpty
            ? null
            : _notesController.text.trim(),
      );
      await ref
          .read(baselineRepositoryProvider)
          .updateBaseline(widget.userId, updated);
      ref.invalidate(_baselineProvider(widget.userId));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Perfil base guardado correctamente')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al guardar: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(_baselineProvider(widget.userId));

    return AppScaffold(
      title: 'Perfil de hábitos',
      body: state.when(
        loading: () => const Center(child: AppLoader()),
        error: (err, _) => AppErrorState(
          message: 'No se pudo cargar el perfil base.',
          onRetry: () => ref.invalidate(_baselineProvider(widget.userId)),
        ),
        data: (profile) {
          _initFromProfile(profile);
          return _Form(
            mood: _mood,
            activityLevel: _activityLevel,
            energyLevel: _energyLevel,
            livesAlone: _livesAlone,
            mealsPerDay: _mealsPerDay,
            sleepHours: _sleepHours,
            socialLevel: _socialLevel,
            notesController: _notesController,
            saving: _saving,
            onChanged: (f, v) => setState(() {
              switch (f) {
                case 'mood': _mood = v as String;
                case 'activity': _activityLevel = v as String;
                case 'energy': _energyLevel = v as String;
                case 'livesAlone': _livesAlone = v as bool;
                case 'meals': _mealsPerDay = v as int;
                case 'sleep': _sleepHours = v as double;
                case 'social': _socialLevel = v as String;
              }
            }),
            onSave: () => _save(profile),
          );
        },
      ),
    );
  }
}

// ── Form widget (keeps build method clean) ──────────────────────────────────

class _Form extends StatelessWidget {
  const _Form({
    required this.mood,
    required this.activityLevel,
    required this.energyLevel,
    required this.livesAlone,
    required this.mealsPerDay,
    required this.sleepHours,
    required this.socialLevel,
    required this.notesController,
    required this.saving,
    required this.onChanged,
    required this.onSave,
  });

  final String mood;
  final String activityLevel;
  final String energyLevel;
  final bool livesAlone;
  final int mealsPerDay;
  final double sleepHours;
  final String socialLevel;
  final TextEditingController notesController;
  final bool saving;
  final void Function(String field, Object value) onChanged;
  final VoidCallback onSave;

  static const _moodOptions = ['positive', 'neutral', 'low'];
  static const _moodLabels = {
    'positive': 'Positivo',
    'neutral': 'Neutro',
    'low': 'Bajo',
  };
  static const _levelOptions = ['low', 'medium', 'high'];
  static const _levelLabels = {
    'low': 'Bajo',
    'medium': 'Medio',
    'high': 'Alto',
  };

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        _Section(
          title: 'Estado de ánimo habitual',
          child: _SegmentedPicker(
            options: _moodOptions,
            labels: _moodLabels,
            value: mood,
            onChanged: (v) => onChanged('mood', v),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        _Section(
          title: 'Nivel de actividad física',
          child: _SegmentedPicker(
            options: _levelOptions,
            labels: _levelLabels,
            value: activityLevel,
            onChanged: (v) => onChanged('activity', v),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        _Section(
          title: 'Nivel de energía habitual',
          child: _SegmentedPicker(
            options: _levelOptions,
            labels: _levelLabels,
            value: energyLevel,
            onChanged: (v) => onChanged('energy', v),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        _Section(
          title: 'Vida social',
          child: _SegmentedPicker(
            options: _levelOptions,
            labels: _levelLabels,
            value: socialLevel,
            onChanged: (v) => onChanged('social', v),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        RitaCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Vive solo',
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      livesAlone ? 'Sí, vive solo/a' : 'No, vive acompañado/a',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ),
                  Switch(
                    value: livesAlone,
                    onChanged: (v) => onChanged('livesAlone', v),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        RitaCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Comidas al día: $mealsPerDay',
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              Slider(
                value: mealsPerDay.toDouble(),
                min: 1,
                max: 7,
                divisions: 6,
                label: '$mealsPerDay',
                onChanged: (v) => onChanged('meals', v.round()),
                activeColor: AppColors.primary,
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        RitaCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Horas de sueño habituales: ${sleepHours.toStringAsFixed(1)}h',
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              Slider(
                value: sleepHours,
                min: 4,
                max: 12,
                divisions: 16,
                label: '${sleepHours.toStringAsFixed(1)}h',
                onChanged: (v) => onChanged('sleep', v),
                activeColor: AppColors.primary,
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        RitaCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Notas del cuidador (opcional)',
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: AppSpacing.sm),
              TextField(
                controller: notesController,
                maxLines: 3,
                decoration: const InputDecoration(
                  hintText: 'Ej: Le gusta salir a caminar por las mañanas...',
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: saving ? null : onSave,
            icon: saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.save_rounded),
            label: Text(saving ? 'Guardando...' : 'Guardar perfil'),
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return RitaCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: AppSpacing.sm),
          child,
        ],
      ),
    );
  }
}

class _SegmentedPicker extends StatelessWidget {
  const _SegmentedPicker({
    required this.options,
    required this.labels,
    required this.value,
    required this.onChanged,
  });

  final List<String> options;
  final Map<String, String> labels;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<String>(
      segments: options
          .map((o) => ButtonSegment<String>(
                value: o,
                label: Text(labels[o] ?? o),
              ))
          .toList(),
      selected: {value},
      onSelectionChanged: (s) => onChanged(s.first),
      style: SegmentedButton.styleFrom(
        selectedBackgroundColor: AppColors.primary,
        selectedForegroundColor: Colors.white,
      ),
    );
  }
}
