import 'package:rita_mobile/core/network/api_client.dart';
import 'package:rita_mobile/features/users/data/models/interpretation_settings.dart';

class InterpretationSettingsApi {
  final ApiClient _client;

  InterpretationSettingsApi(this._client);

  Future<UserInterpretationSettings> getSettings(int userId) async {
    final response = await _client.get('/users/$userId/interpretation-settings');
    return UserInterpretationSettings.fromJson(response);
  }

  Future<UserInterpretationSettings> updateSettings(int userId, UserInterpretationSettings settings) async {
    final response = await _client.put(
      '/users/$userId/interpretation-settings',
      data: settings.toJson(),
    );
    return UserInterpretationSettings.fromJson(response);
  }
}
