import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/users/data/models/user_read.dart';
import 'package:rita_mobile/features/users/data/repository/users_repository.dart';

class UsersController extends StateNotifier<AsyncValue<List<UserRead>>> {
  UsersController(this._repository) : super(const AsyncValue.loading());

  final UsersRepository _repository;

  Future<void> load() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _repository.getUsers());
  }

  Future<void> updateUser(
    int userId, {
    String? fullName,
    String? notes,
    String? profileImageUrl,
  }) async {
    await _repository.updateUser(
      userId,
      fullName: fullName,
      notes: notes,
      profileImageUrl: profileImageUrl,
    );
    await load();
  }

  Future<void> uploadUserPhoto(int userId, String filePath) async {
    await _repository.uploadUserPhoto(userId, filePath);
    await load();
  }
}
