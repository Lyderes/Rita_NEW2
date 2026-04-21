import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../domain/models/scheduled_reminder.dart';
import '../providers/reminders_provider.dart';

class ReminderEditScreen extends ConsumerStatefulWidget {
  final int userId;
  final ScheduledReminder? reminder;

  const ReminderEditScreen({
    super.key,
    required this.userId,
    this.reminder,
  });

  @override
  ConsumerState<ReminderEditScreen> createState() => _ReminderEditScreenState();
}

class _ReminderEditScreenState extends ConsumerState<ReminderEditScreen> {
  final _formKey = GlobalKey<FormState>();
  late String _type;
  late TextEditingController _titleController;
  late TextEditingController _descController;
  late String _time;
  late List<String> _selectedDays;
  late bool _isActive;
  late bool _requiresConfirmation;

  final List<Map<String, dynamic>> _types = [
    {'value': 'medication', 'label': 'Medicación', 'icon': Icons.medication_liquid, 'color': Colors.redAccent},
    {'value': 'meal', 'label': 'Comida', 'icon': Icons.restaurant, 'color': Colors.orange},
    {'value': 'hydration', 'label': 'Hidratación', 'icon': Icons.water_drop, 'color': Colors.blue},
    {'value': 'checkin', 'label': 'Control RITA', 'icon': Icons.record_voice_over, 'color': Colors.teal},
    {'value': 'custom', 'label': 'Otro', 'icon': Icons.notifications_active, 'color': Colors.indigo},
  ];

  final List<String> _allDays = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
  final Map<String, String> _dayLabels = {
    'mon': 'L', 'tue': 'M', 'wed': 'X', 'thu': 'J', 'fri': 'V', 'sat': 'S', 'sun': 'D'
  };

  @override
  void initState() {
    super.initState();
    _type = widget.reminder?.reminderType ?? 'medication';
    _titleController = TextEditingController(text: widget.reminder?.title);
    _descController = TextEditingController(text: widget.reminder?.description);
    _time = widget.reminder?.timeOfDay ?? '09:00';
    _selectedDays = List<String>.from(widget.reminder?.daysOfWeek ?? ['mon', 'tue', 'wed', 'thu', 'fri']);
    _isActive = widget.reminder?.isActive ?? true;
    _requiresConfirmation = widget.reminder?.requiresConfirmation ?? (_type == 'medication');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.reminder == null ? 'Nueva Rutina' : 'Editar Rutina'),
        actions: [
          if (widget.reminder != null)
            IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.red),
              onPressed: _deleteReminder,
            ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            _buildTypeSelector(),
            const SizedBox(height: 32),
            TextFormField(
              controller: _titleController,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              decoration: InputDecoration(
                labelText: 'Título del Recordatorio',
                hintText: 'Ej: Tomar pastilla azul',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                prefixIcon: const Icon(Icons.title),
              ),
              validator: (val) => (val == null || val.isEmpty) ? 'Requerido' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _descController,
              decoration: InputDecoration(
                labelText: 'Notas Adicionales (Opcional)',
                hintText: 'Ej: Después de comer',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                prefixIcon: const Icon(Icons.notes),
              ),
            ),
            const SizedBox(height: 32),
            _buildTimePicker(),
            const SizedBox(height: 32),
            const Text('Frecuencia Semanal', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 12),
            _buildDaySelector(),
            const SizedBox(height: 32),
            _buildSettingsToggles(),
            const SizedBox(height: 48),
            ElevatedButton(
              onPressed: _saveReminder,
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 18),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
              child: Text(
                widget.reminder == null ? 'Crear Rutina' : 'Guardar Cambios',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTypeSelector() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('¿De qué se trata?', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        const SizedBox(height: 12),
        SizedBox(
          height: 90,
          child: ListView(
            scrollDirection: Axis.horizontal,
            children: _types.map((t) {
              final isSelected = _type == t['value'];
              final color = t['color'] as Color;
              return Padding(
                padding: const EdgeInsets.only(right: 12),
                child: ChoiceChip(
                  label: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(t['icon'], color: isSelected ? Colors.white : color),
                      Text(t['label'], style: TextStyle(color: isSelected ? Colors.white : Colors.black87)),
                    ],
                  ),
                  selected: isSelected,
                  selectedColor: color,
                  onSelected: (val) {
                    setState(() {
                      _type = t['value']!;
                      // Auto-suggest confirmation for medication
                      if (_type == 'medication') _requiresConfirmation = true;
                    });
                  },
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildTimePicker() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.blueGrey[50],
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          const Icon(Icons.access_time, color: Colors.blueGrey),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Hora programada', style: TextStyle(fontSize: 13, color: Colors.blueGrey)),
                Text(_time, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
              ],
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              final parts = _time.split(':');
              final initialTime = TimeOfDay(hour: int.parse(parts[0]), minute: int.parse(parts[1]));
              final selected = await showTimePicker(context: context, initialTime: initialTime);
              if (selected != null) {
                setState(() {
                  _time = '${selected.hour.toString().padLeft(2, '0')}:${selected.minute.toString().padLeft(2, '0')}';
                });
              }
            },
            style: ElevatedButton.styleFrom(elevation: 0),
            child: const Text('Cambiar'),
          ),
        ],
      ),
    );
  }

  Widget _buildDaySelector() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: _allDays.map((d) {
        final isSelected = _selectedDays.contains(d);
        return GestureDetector(
          onTap: () {
            setState(() {
              if (isSelected) {
                _selectedDays.remove(d);
              } else {
                _selectedDays.add(d);
              }
            });
          },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: isSelected ? Theme.of(context).primaryColor : Colors.white,
              border: Border.all(color: isSelected ? Theme.of(context).primaryColor : Colors.grey[300]!),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                _dayLabels[d]!,
                style: TextStyle(
                  color: isSelected ? Colors.white : Colors.black87,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSettingsToggles() {
    return Column(
      children: [
        SwitchListTile.adaptive(
          title: const Text('Confirmación requerida'),
          subtitle: const Text('RITA esperará que el usuario confirme verbalmente.'),
          value: _requiresConfirmation,
          onChanged: (val) => setState(() => _requiresConfirmation = val),
        ),
        SwitchListTile.adaptive(
          title: const Text('Recordatorio activo'),
          subtitle: const Text('Desactívalo temporalmente sin borrarlo.'),
          value: _isActive,
          onChanged: (val) => setState(() => _isActive = val),
        ),
      ],
    );
  }

  void _saveReminder() async {
    if (!_formKey.currentState!.validate()) return;
    if (_selectedDays.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Por favor, elige al menos un día.')),
      );
      return;
    }

    final data = {
      'reminder_type': _type,
      'title': _titleController.text,
      'description': _descController.text,
      'time_of_day': _time,
      'days_of_week': _selectedDays,
      'is_active': _isActive,
      'requires_confirmation': _requiresConfirmation,
    };

    if (widget.reminder == null) {
      await ref.read(remindersProvider(widget.userId).notifier).addReminder(data);
    } else {
      await ref.read(remindersProvider(widget.userId).notifier).updateReminder(widget.reminder!.id, data);
    }

    if (mounted) Navigator.pop(context);
  }

  void _deleteReminder() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('¿Eliminar esta rutina?'),
        content: const Text('Esta acción quitará el recordatorio permanentemente.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Mantener')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Eliminar', style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );

    if (confirm == true) {
      await ref.read(remindersProvider(widget.userId).notifier).deleteReminder(widget.reminder!.id);
      if (mounted) Navigator.pop(context);
    }
  }
}
