import 'package:dio/dio.dart';
import 'package:rita_mobile/core/network/api_client.dart';
import 'package:rita_mobile/features/users/data/models/daily_score.dart';
import 'package:rita_mobile/features/users/data/models/user_baseline_profile.dart';
import 'package:rita_mobile/features/users/data/models/user_overview_read.dart';
import 'package:rita_mobile/features/users/data/models/user_read.dart';
import 'package:rita_mobile/features/users/data/models/user_status_read.dart';
import 'package:rita_mobile/features/users/data/models/user_timeline_read.dart';
import 'package:rita_mobile/features/users/data/models/interpretation_settings.dart';

class UsersApi {
  UsersApi(this._client);

  final ApiClient _client;

  Future<List<UserRead>> fetchUsers() async {
    final response = await _client.get('/users');

    if (response is! List<dynamic>) {
      throw Exception('Invalid users response');
    }

    return response
        .whereType<Map<String, dynamic>>()
        .map(UserRead.fromJson)
        .toList();
  }

  Future<UserRead> fetchUserById(int userId) async {
    final response = await _client.get('/users/$userId');

    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid user response');
    }

    return UserRead.fromJson(response);
  }

  Future<UserRead> updateUser(
    int userId, {
    String? fullName,
    String? notes,
    String? profileImageUrl,
  }) async {
    final response = await _client.put(
      '/users/$userId',
      data: {
        if (fullName != null) 'full_name': fullName,
        if (notes != null) 'notes': notes,
        if (profileImageUrl != null) 'profile_image_url': profileImageUrl,
      },
    );

    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid update user response');
    }

    return UserRead.fromJson(response);
  }

  Future<UserRead> uploadUserPhoto(int userId, String filePath) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(
        filePath,
        filename: filePath.split('/').last,
      ),
    });

    final response = await _client.post(
      '/users/$userId/photo',
      data: formData,
    );

    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid photo upload response');
    }

    return UserRead.fromJson(response);
  }

  Future<UserStatusRead> fetchUserStatus(int userId) async {
    final response = await _client.get('/users/$userId/status');
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid user status response');
    }
    return UserStatusRead.fromJson(response);
  }

  Future<UserOverviewRead> fetchUserOverview(int userId) async {
    final response = await _client.get('/users/$userId/overview');
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid user overview response');
    }
    return UserOverviewRead.fromJson(response);
  }

  Future<UserTimelineRead> fetchUserTimeline(int userId, {int limit = 10}) async {
    final response = await _client.get(
      '/users/$userId/timeline',
      queryParameters: {'limit': limit},
    );
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid user timeline response');
    }
    return UserTimelineRead.fromJson(response);
  }

  Future<UserBaselineProfile> fetchUserBaseline(int userId) async {
    final response = await _client.get('/users/$userId/baseline');
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid baseline response');
    }
    return UserBaselineProfile.fromJson(response);
  }

  Future<UserBaselineProfile> updateUserBaseline(int userId, UserBaselineProfile baseline) async {
    final response = await _client.put(
      '/users/$userId/baseline',
      data: baseline.toJson(),
    );
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid baseline update response');
    }
    return UserBaselineProfile.fromJson(response);
  }

  Future<DailyScore> fetchLatestDailyScore(int userId) async {
    final response = await _client.get('/users/$userId/daily-score/latest');
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid daily score response');
    }
    return DailyScore.fromJson(response);
  }

  Future<List<DailyScore>> fetchDailyScoreHistory(int userId, {int limit = 7}) async {
    final response = await _client.get(
      '/users/$userId/daily-score/history',
      queryParameters: {'limit': limit},
    );

    if (response is! List<dynamic>) {
      throw Exception('Invalid daily score history response');
    }

    return response
        .whereType<Map<String, dynamic>>()
        .map(DailyScore.fromJson)
        .toList();
  }

  Future<UserInterpretationSettings> fetchUserInterpretationSettings(int userId) async {
    final response = await _client.get('/users/$userId/interpretation-settings');
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid interpretation settings response');
    }
    return UserInterpretationSettings.fromJson(response);
  }

  Future<UserInterpretationSettings> updateUserInterpretationSettings(
    int userId,
    UserInterpretationSettings settings,
  ) async {
    final response = await _client.put(
      '/users/$userId/interpretation-settings',
      data: settings.toJson(),
    );
    if (response is! Map<String, dynamic>) {
      throw Exception('Invalid interpretation settings update response');
    }
    return UserInterpretationSettings.fromJson(response);
  }

  Future<void> confirmReminder(int eventId) async {
    await _client.post('/events/$eventId/confirm');
  }
}
