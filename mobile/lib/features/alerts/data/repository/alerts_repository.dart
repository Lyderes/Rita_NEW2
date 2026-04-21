import 'package:rita_mobile/features/alerts/data/api/alerts_api.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';
import 'package:rita_mobile/shared/models/paginated_response.dart';

class AlertsRepository {
  AlertsRepository(this._api);

  final AlertsApi _api;

  Future<PaginatedResponse<AlertRead>> getAlerts() {
    return _api.fetchAlerts();
  }

  Future<AlertRead> getAlertById(int alertId) {
    return _api.fetchAlertById(alertId);
  }

  Future<AlertRead> acknowledgeAlert(int alertId) {
    return _api.acknowledgeAlert(alertId);
  }

  Future<AlertRead> resolveAlert(int alertId) {
    return _api.resolveAlert(alertId);
  }

  Future<void> deleteAlert(int alertId) {
    return _api.deleteAlert(alertId);
  }
}
