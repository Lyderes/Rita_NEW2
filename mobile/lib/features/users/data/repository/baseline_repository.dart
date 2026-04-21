
import 'package:rita_mobile/features/users/data/api/users_api.dart';
import 'package:rita_mobile/features/users/data/models/user_baseline_profile.dart';

class BaselineRepository {
  BaselineRepository(this._api);

  final UsersApi _api;

  Future<UserBaselineProfile> getBaseline(int userId) {
    return _api.fetchUserBaseline(userId);
  }

  Future<UserBaselineProfile> updateBaseline(int userId, UserBaselineProfile baseline) {
    return _api.updateUserBaseline(userId, baseline);
  }
}
