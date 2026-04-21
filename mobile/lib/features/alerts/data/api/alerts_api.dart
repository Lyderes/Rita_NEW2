import 'package:rita_mobile/core/network/api_client.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';
import 'package:rita_mobile/shared/models/paginated_response.dart';

class AlertsApi {
  AlertsApi(this._client);

  final ApiClient _client;

  Future<PaginatedResponse<AlertRead>> fetchAlerts({
    int limit = 20,
    int offset = 0,
  }) async {
    final response = await _client.get(
      '/alerts',
      queryParameters: {'limit': limit, 'offset': offset},
    );

    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid alerts response');
    }

    return PaginatedResponse<AlertRead>.fromJson(response, AlertRead.fromJson);
  }

  Future<AlertRead> fetchAlertById(int alertId) async {
    final response = await _client.get('/alerts/$alertId');
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid alert detail response');
    }
    return AlertRead.fromJson(response);
  }

  Future<AlertRead> acknowledgeAlert(int alertId) async {
    final response = await _client.patch('/alerts/$alertId/acknowledge');
    _validateAlertActionResponse(response);
    return fetchAlertById(alertId);
  }

  Future<AlertRead> resolveAlert(int alertId) async {
    final response = await _client.patch('/alerts/$alertId/resolve');
    _validateAlertActionResponse(response);
    return fetchAlertById(alertId);
  }

  Future<void> deleteAlert(int alertId) async {
    await _client.delete('/alerts/$alertId');
  }

  void _validateAlertActionResponse(dynamic response) {
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid alert action response');
    }

    if (!response.containsKey('id') ||
        !response.containsKey('status') ||
        !response.containsKey('sent_at')) {
      throw Exception('Unexpected alert action schema');
    }
  }
}
