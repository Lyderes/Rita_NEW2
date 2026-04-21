import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../domain/models/scheduled_reminder.dart';
import '../providers/reminders_provider.dart';
import 'reminder_edit_screen.dart';

class RemindersListScreen extends ConsumerWidget {
  final int userId;
  final String userName;

  const RemindersListScreen({
    super.key,
    required this.userId,
    required this.userName,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final remindersAsync = ref.watch(remindersProvider(userId));

    return Scaffold(
      backgroundColor: const Color(0xFFF8F9FA),
      appBar: AppBar(
        title: Text('Rutinas de $userName'),
        elevation: 0,
        backgroundColor: Colors.white,
        foregroundColor: Colors.black87,
      ),
      body: remindersAsync.when(
        data: (reminders) => reminders.isEmpty
            ? _buildEmptyState(context)
            : _buildList(context, ref, reminders),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, stack) => Center(child: Text('Error: $err')),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showEditScreen(context),
        icon: const Icon(Icons.add_task),
        label: const Text('Nueva Rutina'),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.blue.withOpacity(0.05),
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.calendar_today_outlined, size: 64, color: Colors.blue[200]),
          ),
          const SizedBox(height: 24),
          Text(
            'Organiza el día de $userName',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: Colors.blueGrey[800],
            ),
          ),
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Text(
              'Añade recordatorios de medicación, comidas o hidratación para que RITA le acompañe.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.blueGrey[600], fontSize: 16),
            ),
          ),
          const SizedBox(height: 32),
          ElevatedButton(
            onPressed: () => _showEditScreen(context),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(30)),
            ),
            child: const Text('Empezar ahora'),
          ),
        ],
      ),
    );
  }

  Widget _buildList(BuildContext context, WidgetRef ref, List<ScheduledReminder> reminders) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
      itemCount: reminders.length,
      itemBuilder: (context, index) {
        final reminder = reminders[index];
        return _ReminderCard(
          reminder: reminder,
          onToggle: (val) {
            ref.read(remindersProvider(userId).notifier).toggleReminder(reminder);
          },
          onTap: () => _showEditScreen(context, reminder: reminder),
        );
      },
    );
  }

  void _showEditScreen(BuildContext context, {ScheduledReminder? reminder}) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => ReminderEditScreen(
          userId: userId,
          reminder: reminder,
        ),
      ),
    );
  }
}

class _ReminderCard extends StatelessWidget {
  final ScheduledReminder reminder;
  final ValueChanged<bool> onToggle;
  final VoidCallback onTap;

  const _ReminderCard({
    required this.reminder,
    required this.onToggle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = _getStyleForType(reminder.reminderType);
    
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: Colors.grey.withOpacity(0.1)),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: theme.color.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(theme.icon, color: theme.color, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            reminder.title,
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                              color: reminder.isActive ? Colors.blueGrey[900] : Colors.grey,
                              decoration: reminder.isActive ? null : TextDecoration.lineThrough,
                            ),
                          ),
                        ),
                        if (reminder.requiresConfirmation)
                          Container(
                            margin: const EdgeInsets.only(left: 4),
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.blue.withOpacity(0.1),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'CONFIRMAR',
                              style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Colors.blue),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(Icons.access_time, size: 14, color: Colors.grey[600]),
                        const SizedBox(width: 4),
                        Text(
                          reminder.timeOfDay,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: Colors.grey[800],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Icon(Icons.repeat, size: 14, color: Colors.grey[600]),
                        const SizedBox(width: 4),
                        Text(
                          _getDisplayDays(reminder.daysOfWeek),
                          style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Switch.adaptive(
                value: reminder.isActive,
                onChanged: onToggle,
                activeColor: theme.color,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _getDisplayDays(List<String> days) {
    if (days.length == 7) return 'Diario';
    if (days.length == 5 && !days.contains('sat') && !days.contains('sun')) return 'Lun-Vie';
    if (days.length == 2 && days.contains('sat') && days.contains('sun')) return 'Fines de semana';
    
    final labels = {'mon': 'L', 'tue': 'M', 'wed': 'X', 'thu': 'J', 'fri': 'V', 'sat': 'S', 'sun': 'D'};
    return days.map((d) => labels[d]).join(', ');
  }

  _ReminderTypeTheme _getStyleForType(String type) {
    switch (type) {
      case 'medication':
        return const _ReminderTypeTheme(Icons.medication_liquid, Colors.redAccent);
      case 'meal':
        return const _ReminderTypeTheme(Icons.restaurant, Colors.orange);
      case 'hydration':
        return const _ReminderTypeTheme(Icons.water_drop, Colors.blue);
      case 'checkin':
        return const _ReminderTypeTheme(Icons.record_voice_over, Colors.teal);
      default:
        return const _ReminderTypeTheme(Icons.notifications_active, Colors.indigo);
    }
  }
}

class _ReminderTypeTheme {
  final IconData icon;
  final Color color;
  const _ReminderTypeTheme(this.icon, this.color);
}
