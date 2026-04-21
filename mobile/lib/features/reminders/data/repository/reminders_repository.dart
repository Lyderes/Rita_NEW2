import '../../domain/models/scheduled_reminder.dart';
import '../api/reminders_api.dart';

class RemindersRepository {
  final RemindersApi _api;

  RemindersRepository(this._api);

  Future<List<ScheduledReminder>> listReminders(int userId) {
    return _api.listReminders(userId);
  }

  Future<ScheduledReminder> createReminder(int userId, Map<String, dynamic> data) {
    return _api.createReminder(userId, data);
  }

  Future<ScheduledReminder> updateReminder(int reminderId, Map<String, dynamic> data) {
    return _api.updateReminder(reminderId, data);
  }

  Future<void> deleteReminder(int reminderId) {
    return _api.deleteReminder(reminderId);
  }
}
