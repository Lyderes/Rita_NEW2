import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/errors/api_error.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';
import 'package:rita_mobile/features/alerts/data/repository/alerts_repository.dart';
import 'package:rita_mobile/features/alerts/presentation/providers/alerts_provider.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

class AlertDetailController extends StateNotifier<AsyncValue<AlertRead>> {
  AlertDetailController(this._repository, this._alertId)
  : super(const AsyncValue.loading()) {
    load();
  }

  final AlertsRepository _repository;
  final int _alertId;

  Future<void> load() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _repository.getAlertById(_alertId));
  }
}

final alertDetailProvider = StateNotifierProvider.family<
    AlertDetailController, AsyncValue<AlertRead>, int>((ref, alertId) {
  return AlertDetailController(ref.read(alertsRepositoryProvider), alertId);
});

final alertDetailFamilyProvider = Provider.family<AsyncValue<AlertRead>, int>(
  (ref, alertId) {
    return ref.watch(alertDetailProvider(alertId));
  },
);

class AcknowledgeAlertNotifier extends FamilyAsyncNotifier<void, int> {
  @override
  Future<void> build(int arg) async {}

  Future<void> acknowledge() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await ref.read(alertsRepositoryProvider).acknowledgeAlert(arg);
      ref.invalidate(alertDetailProvider(arg));
      ref.invalidate(alertDetailFamilyProvider(arg));
      ref.invalidate(alertsControllerProvider);
    });
  }
}

final acknowledgeAlertProvider =
    AsyncNotifierProvider.family<AcknowledgeAlertNotifier, void, int>(
  AcknowledgeAlertNotifier.new,
);

class ResolveAlertNotifier extends FamilyAsyncNotifier<void, int> {
  @override
  Future<void> build(int arg) async {}

  Future<void> resolve() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await ref.read(alertsRepositoryProvider).resolveAlert(arg);
      ref.invalidate(alertDetailProvider(arg));
      ref.invalidate(alertDetailFamilyProvider(arg));
      ref.invalidate(alertsControllerProvider);
    });
  }
}

final resolveAlertProvider =
    AsyncNotifierProvider.family<ResolveAlertNotifier, void, int>(
  ResolveAlertNotifier.new,
);

String extractAlertErrorMessage(Object error) {
  if (error is ApiError && error.message.isNotEmpty) {
    return error.message;
  }
  return 'Unable to process alert action';
}
