import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/users/data/models/user_read.dart';
import 'package:rita_mobile/features/users/data/state/users_state.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

final usersControllerProvider =
		StateNotifierProvider<UsersController, AsyncValue<List<UserRead>>>((ref) {
	final controller = UsersController(ref.watch(usersRepositoryProvider));
	controller.load();
	return controller;
});
