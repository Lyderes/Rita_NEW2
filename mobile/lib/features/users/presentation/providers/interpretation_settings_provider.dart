import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/users/data/models/interpretation_settings.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

class InterpretationSettingsNotifier
    extends FamilyAsyncNotifier<UserInterpretationSettings, int> {
  @override
  Future<UserInterpretationSettings> build(int arg) async {
    return ref.read(usersRepositoryProvider).getInterpretationSettings(arg);
  }

  Future<void> updateSettings(UserInterpretationSettings settings) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      return ref
          .read(usersRepositoryProvider)
          .updateSettings(arg, settings);
    });
  }
}

final interpretationSettingsProvider = AsyncNotifierProvider.family<
    InterpretationSettingsNotifier, UserInterpretationSettings, int>(
  InterpretationSettingsNotifier.new,
);
