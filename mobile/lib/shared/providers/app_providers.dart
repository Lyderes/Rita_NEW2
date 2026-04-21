import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/config/env.dart';
import 'package:rita_mobile/core/network/api_client.dart';
import 'package:rita_mobile/core/services/push_notification_service.dart';
import 'package:rita_mobile/core/storage/secure_storage_service.dart';
import 'package:rita_mobile/features/alerts/data/api/alerts_api.dart';
import 'package:rita_mobile/features/alerts/data/repository/alerts_repository.dart';
import 'package:rita_mobile/features/auth/data/api/auth_api.dart';
import 'package:rita_mobile/features/auth/data/repository/auth_repository.dart';
import 'package:rita_mobile/features/auth/data/state/auth_state.dart';
import 'package:rita_mobile/features/auth/presentation/providers/auth_provider.dart';
import 'package:rita_mobile/features/users/data/api/users_api.dart';
import 'package:rita_mobile/features/users/data/repository/baseline_repository.dart';
import 'package:rita_mobile/features/users/data/repository/users_repository.dart';
import 'package:rita_mobile/features/conversations/data/api/conversations_api.dart';
import 'package:rita_mobile/features/reminders/data/api/reminders_api.dart';
import 'package:rita_mobile/features/reminders/data/repository/reminders_repository.dart';

final Provider<SecureStorageService> secureStorageProvider =
    Provider<SecureStorageService>((ref) {
  return SecureStorageService();
});

final Provider<ApiClient> apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(
    baseUrl: Env.apiBaseUrl,
    secureStorage: ref.watch(secureStorageProvider),
    onUnauthorized: () {
      ref.read(authControllerProvider.notifier).invalidateSession();
    },
  );
});

final Provider<AuthApi> authApiProvider = Provider<AuthApi>((ref) {
  return AuthApi(ref.watch(apiClientProvider));
});

final Provider<PushNotificationService> pushNotificationServiceProvider =
    Provider<PushNotificationService>((_) => PushNotificationService.instance);

final Provider<AuthRepository> authRepositoryProvider =
    Provider<AuthRepository>((ref) {
  return AuthRepository(
    api: ref.watch(authApiProvider),
    storage: ref.watch(secureStorageProvider),
    pushNotifications: ref.watch(pushNotificationServiceProvider),
  );
});

final StateNotifierProvider<AuthController, AuthState> authControllerProvider =
    StateNotifierProvider<AuthController, AuthState>((ref) {
  final controller = AuthController(ref.watch(authRepositoryProvider));
  controller.bootstrap();
  return controller;
});

final Provider<AlertsApi> alertsApiProvider = Provider<AlertsApi>((ref) {
  return AlertsApi(ref.watch(apiClientProvider));
});

final Provider<AlertsRepository> alertsRepositoryProvider =
    Provider<AlertsRepository>((ref) {
  return AlertsRepository(ref.watch(alertsApiProvider));
});

final Provider<UsersApi> usersApiProvider = Provider<UsersApi>((ref) {
  return UsersApi(ref.watch(apiClientProvider));
});

final Provider<UsersRepository> usersRepositoryProvider =
    Provider<UsersRepository>((ref) {
  return UsersRepository(ref.watch(usersApiProvider));
});

final Provider<BaselineRepository> baselineRepositoryProvider =
    Provider<BaselineRepository>((ref) {
  return BaselineRepository(ref.watch(usersApiProvider));
});

final Provider<RemindersApi> remindersApiProvider = Provider<RemindersApi>((ref) {
  return RemindersApi(ref.watch(apiClientProvider).dio);
});

final Provider<RemindersRepository> remindersRepositoryProvider =
    Provider<RemindersRepository>((ref) {
  return RemindersRepository(ref.watch(remindersApiProvider));
});

final Provider<ConversationsApi> conversationsApiProvider =
    Provider<ConversationsApi>((ref) {
  return ConversationsApi(ref.watch(apiClientProvider));
});
