import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';
import 'package:rita_mobile/features/alerts/data/repository/alerts_repository.dart';
import 'package:rita_mobile/shared/models/paginated_response.dart';

class AlertsController
    extends StateNotifier<AsyncValue<PaginatedResponse<AlertRead>>> {
  AlertsController(this._repository) : super(const AsyncValue.loading());

  final AlertsRepository _repository;

  Future<void> load() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(_repository.getAlerts);
  }

  Future<void> refreshSilently() async {
    state = await AsyncValue.guard(_repository.getAlerts);
  }
}
