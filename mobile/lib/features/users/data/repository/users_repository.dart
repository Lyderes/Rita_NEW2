import 'package:rita_mobile/core/errors/api_error.dart';
import 'package:rita_mobile/features/users/data/api/users_api.dart';
import 'package:rita_mobile/features/users/data/models/daily_score.dart';
import 'package:rita_mobile/features/users/data/models/interpretation_settings.dart';
import 'package:rita_mobile/features/users/data/models/user_detail_bundle.dart';
import 'package:rita_mobile/features/users/data/models/user_overview_read.dart';
import 'package:rita_mobile/features/users/data/models/user_read.dart';
import 'package:rita_mobile/features/users/data/models/user_status_read.dart';
import 'package:rita_mobile/features/users/data/models/user_timeline_read.dart';

class UsersRepository {
  UsersRepository(this._api);

  final UsersApi _api;

  Future<List<UserRead>> getUsers() {
    return _api.fetchUsers();
  }

  Future<UserRead> getUserById(int userId) async {
    try {
      return await _api.fetchUserById(userId);
    } on ApiError catch (e) {
      // Backends that predate GET /users/{id} return 405 — fall back to list
      if (e.code == 405) {
        final users = await _api.fetchUsers();
        return users.firstWhere(
          (u) => u.id == userId,
          orElse: () => throw Exception('User $userId not found'),
        );
      }
      rethrow;
    }
  }

  Future<UserStatusRead> getUserStatus(int userId) {
    return _api.fetchUserStatus(userId);
  }

  Future<UserOverviewRead> getUserOverview(int userId) {
    return _api.fetchUserOverview(userId);
  }

  Future<UserTimelineRead> getUserTimeline(int userId, {int limit = 10}) {
    return _api.fetchUserTimeline(userId, limit: limit);
  }

  Future<List<DailyScore>> getDailyScoreHistory(int userId, {int limit = 7}) {
    return _api.fetchDailyScoreHistory(userId, limit: limit);
  }

  Future<DailyScore> getLatestDailyScore(int userId) {
    return _api.fetchLatestDailyScore(userId);
  }

  Future<UserDetailBundle> getUserDetailBundle(int userId) async {
    final userFuture = getUserById(userId);
    final statusFuture = getUserStatus(userId);
    final overviewFuture = getUserOverview(userId);
    final timelineFuture = getUserTimeline(userId, limit: 10);
    final scoresFuture = getDailyScoreHistory(userId, limit: 7);

    final user = await userFuture;
    final status = await statusFuture;
    final overview = await overviewFuture;
    final timeline = await timelineFuture;
    final scores = await scoresFuture;

    return UserDetailBundle(
      user: user,
      status: status,
      overview: overview,
      timeline: timeline,
      dailyScores: scores,
    );
  }

  Future<UserInterpretationSettings> getInterpretationSettings(int userId) {
    return _api.fetchUserInterpretationSettings(userId);
  }

  Future<UserInterpretationSettings> updateInterpretationSettings(int userId, UserInterpretationSettings settings) {
    return _api.updateUserInterpretationSettings(userId, settings);
  }

  Future<UserInterpretationSettings> updateSettings(int userId, UserInterpretationSettings settings) {
    return updateInterpretationSettings(userId, settings);
  }

  Future<UserRead> updateUser(
    int userId, {
    String? fullName,
    String? notes,
    String? profileImageUrl,
  }) {
    return _api.updateUser(
      userId,
      fullName: fullName,
      notes: notes,
      profileImageUrl: profileImageUrl,
    );
  }

  Future<UserRead> uploadUserPhoto(int userId, String filePath) {
    return _api.uploadUserPhoto(userId, filePath);
  }
}
