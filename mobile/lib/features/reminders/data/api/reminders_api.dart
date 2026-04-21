import 'package:dio/dio.dart';
import '../../domain/models/scheduled_reminder.dart';

class RemindersApi {
  final Dio _dio;

  RemindersApi(this._dio);

  Future<List<ScheduledReminder>> listReminders(int userId) async {
    final response = await _dio.get('/users/$userId/reminders');
    return (response.data as List)
        .map((e) => ScheduledReminder.fromJson(e))
        .toList();
  }

  Future<ScheduledReminder> createReminder(int userId, Map<String, dynamic> data) async {
    final response = await _dio.post('/users/$userId/reminders', data: data);
    return ScheduledReminder.fromJson(response.data);
  }

  Future<ScheduledReminder> updateReminder(int reminderId, Map<String, dynamic> data) async {
    final response = await _dio.put('/reminders/$reminderId', data: data);
    return ScheduledReminder.fromJson(response.data);
  }

  Future<void> deleteReminder(int reminderId) async {
    await _dio.delete('/reminders/$reminderId');
  }
}
