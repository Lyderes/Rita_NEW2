import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/errors/api_error.dart';
import 'package:rita_mobile/features/users/data/models/user_detail_bundle.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

class UserDetailNotifier extends FamilyAsyncNotifier<UserDetailBundle, int> {
  @override
  Future<UserDetailBundle> build(int arg) async {
    return ref.read(usersRepositoryProvider).getUserDetailBundle(arg);
  }

  Future<void> reload() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(usersRepositoryProvider).getUserDetailBundle(arg),
    );
  }
}

final userDetailProvider =
    AsyncNotifierProvider.family<UserDetailNotifier, UserDetailBundle, int>(
  UserDetailNotifier.new,
);

String extractUserDetailErrorMessage(Object error) {
  if (error is ApiError && error.message.isNotEmpty) {
    return error.message;
  }
  return 'No se pudo cargar el detalle del usuario';
}
