import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/users/data/models/interpretation_settings.dart';
import 'package:rita_mobile/features/users/presentation/providers/interpretation_settings_provider.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';
import 'package:rita_mobile/shared/widgets/app_error_state.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';

class InterpretationSettingsScreen extends ConsumerWidget {
  final int userId;

  const InterpretationSettingsScreen({super.key, required this.userId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settingsAsync = ref.watch(interpretationSettingsProvider(userId));

    return AppScaffold(
      title: 'Personalización de RITA',
      body: settingsAsync.when(
        data: (settings) => _SettingsContent(userId: userId, settings: settings),
        loading: () => const Center(child: AppLoader()),
        error: (err, stack) => Padding(
          padding: const EdgeInsets.all(16),
          child: AppErrorState(
            message: 'No se pudo cargar la configuración de RITA.\n$err',
            onRetry: () => ref.invalidate(interpretationSettingsProvider(userId)),
          ),
        ),
      ),
    );
  }
}

class _SettingsContent extends ConsumerStatefulWidget {
  final int userId;
  final UserInterpretationSettings settings;

  const _SettingsContent({required this.userId, required this.settings});

  @override
  ConsumerState<_SettingsContent> createState() => _SettingsContentState();
}

class _SettingsContentState extends ConsumerState<_SettingsContent> {
  late UserInterpretationSettings _currentSettings;

  @override
  void initState() {
    super.initState();
    _currentSettings = widget.settings;
  }

  void _updateMode(String? mode) {
    if (mode == null) return;
    setState(() {
      _currentSettings = _currentSettings.copyWith(sensitivityMode: mode);
    });
  }

  void _toggleFlag(String flag, bool? value) {
    if (value == null) return;
    setState(() {
      switch (flag) {
        case 'chronic_pain':
          _currentSettings = _currentSettings.copyWith(hasChronicPain: value);
          break;
        case 'low_energy':
          _currentSettings = _currentSettings.copyWith(lowEnergyBaseline: value);
          break;
        case 'mood':
          _currentSettings = _currentSettings.copyWith(moodVariability: value);
          break;
        case 'comm':
          _currentSettings = _currentSettings.copyWith(lowCommunication: value);
          break;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Sensibilidad de RITA',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        const Text(
          'Ajusta qué tan pronto RITA debe avisar ante desviaciones en la rutina.',
          style: TextStyle(color: Colors.grey),
        ),
        const SizedBox(height: 16),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(value: 'calm', label: Text('Tranquilo'), icon: Icon(Icons.sentiment_satisfied)),
            ButtonSegment(value: 'balanced', label: Text('Equilibrado'), icon: Icon(Icons.balance)),
            ButtonSegment(value: 'sensitive', label: Text('Sensible'), icon: Icon(Icons.shutter_speed)),
          ],
          selected: {_currentSettings.sensitivityMode},
          onSelectionChanged: (val) => _updateMode(val.first),
        ),
        const SizedBox(height: 32),
        Text(
          'Sobre esta persona',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        const Text(
          'Marca las condiciones habituales para que RITA ajuste sus expectativas.',
          style: TextStyle(color: Colors.grey),
        ),
        const SizedBox(height: 8),
        CheckboxListTile(
          title: const Text('Tiene dolor físico crónico'),
          subtitle: const Text('Reduce la alarma por avisos de dolor, pero vigila empeoramientos.'),
          value: _currentSettings.hasChronicPain,
          onChanged: (val) => _toggleFlag('chronic_pain', val),
        ),
        CheckboxListTile(
          title: const Text('Suele tener poca energía'),
          subtitle: const Text('Ajusta el umbral de actividad física habitual.'),
          value: _currentSettings.lowEnergyBaseline,
          onChanged: (val) => _toggleFlag('low_energy', val),
        ),
        CheckboxListTile(
          title: const Text('Su ánimo varía a menudo'),
          subtitle: const Text('Reduce la penalización por volatilidad emocional.'),
          value: _currentSettings.moodVariability,
          onChanged: (val) => _toggleFlag('mood', val),
        ),
        CheckboxListTile(
          title: const Text('Se comunica poco habitualmente'),
          subtitle: const Text('Ajusta la frecuencia esperada de mensajes.'),
          value: _currentSettings.lowCommunication,
          onChanged: (val) => _toggleFlag('comm', val),
        ),
        const SizedBox(height: 48),
        ElevatedButton(
          onPressed: () async {
            await ref
                .read(interpretationSettingsProvider(widget.userId).notifier)
                .updateSettings(_currentSettings);
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Configuración guardada correctamente')),
              );
              Navigator.pop(context);
            }
          },
          child: const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text('Guardar Personalización'),
          ),
        ),
      ],
    );
  }
}
