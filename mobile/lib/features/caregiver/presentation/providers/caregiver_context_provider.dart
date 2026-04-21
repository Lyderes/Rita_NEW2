import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/users/data/models/user_read.dart';
import 'package:rita_mobile/features/users/presentation/providers/users_provider.dart';

// Hidden override kept for future multi-profile support.
final caregiverActiveUserIdOverrideProvider = StateProvider<int?>((ref) => null);

final caregiverActiveUserProvider = Provider<UserRead?>((ref) {
  final usersState = ref.watch(usersControllerProvider);
  final selectedId = ref.watch(caregiverActiveUserIdOverrideProvider);

  return usersState.maybeWhen(
    data: (users) {
      if (users.isEmpty) {
        return null;
      }
      if (selectedId == null) {
        return users.first;
      }
      for (final user in users) {
        if (user.id == selectedId) {
          return user;
        }
      }
      return users.first;
    },
    orElse: () => null,
  );
});

// Backward-compatible aliases for existing code paths.
final caregiverSelectedUserIdProvider = caregiverActiveUserIdOverrideProvider;
final caregiverSelectedUserProvider = caregiverActiveUserProvider;
