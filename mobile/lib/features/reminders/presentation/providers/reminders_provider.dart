import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';
import '../../domain/models/scheduled_reminder.dart';

final remindersProvider = AsyncNotifierProvider.family<RemindersNotifier, List<ScheduledReminder>, int>(
  RemindersNotifier.new,
);

class RemindersNotifier extends FamilyAsyncNotifier<List<ScheduledReminder>, int> {
  @override
  FutureOr<List<ScheduledReminder>> build(int arg) async {
    return ref.watch(remindersRepositoryProvider).listReminders(arg);
  }

  Future<void> addReminder(Map<String, dynamic> data) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(remindersRepositoryProvider).createReminder(arg, data);
      return ref.read(remindersRepositoryProvider).listReminders(arg);
    });
  }

  Future<void> updateReminder(int reminderId, Map<String, dynamic> data) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(remindersRepositoryProvider).updateReminder(reminderId, data);
      return ref.read(remindersRepositoryProvider).listReminders(arg);
    });
  }

  Future<void> deleteReminder(int reminderId) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(remindersRepositoryProvider).deleteReminder(reminderId);
      return ref.read(remindersRepositoryProvider).listReminders(arg);
    });
  }

  Future<void> toggleReminder(ScheduledReminder reminder) async {
    await updateReminder(reminder.id, {'is_active': !reminder.isActive});
  }
}
