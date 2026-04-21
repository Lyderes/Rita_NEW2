import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/errors/api_error.dart';
import 'package:rita_mobile/features/auth/data/repository/auth_repository.dart';
import 'package:rita_mobile/features/auth/data/state/auth_state.dart';

class AuthController extends StateNotifier<AuthState> {
  AuthController(this._repository) : super(AuthState.initial);

  final AuthRepository _repository;

  Future<void> bootstrap() async {
    final hasSession = await _repository.hasSession();
    state = state.copyWith(
      status: hasSession ? AuthStatus.authenticated : AuthStatus.unauthenticated,
      errorMessage: null,
    );
  }

  Future<bool> login({required String username, required String password}) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      await _repository.login(username: username, password: password);
      state = state.copyWith(
        status: AuthStatus.authenticated,
        isLoading: false,
      );
      return true;
    } on ApiError catch (error) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        isLoading: false,
        errorMessage: error.message,
      );
      return false;
    } catch (_) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        isLoading: false,
        errorMessage: 'Unable to sign in',
      );
      return false;
    }
  }

  Future<bool> register({
    required String username,
    required String password,
    String? fullName,
  }) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      await _repository.register(
        username: username,
        password: password,
        fullName: fullName,
      );
      state = state.copyWith(
        status: AuthStatus.authenticated,
        isLoading: false,
      );
      return true;
    } on ApiError catch (error) {
      final message = error.code == 409
          ? 'Ese usuario ya existe. Inicia sesion o usa otro nombre de usuario.'
          : error.message;
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        isLoading: false,
        errorMessage: message,
      );
      return false;
    } catch (_) {
      state = state.copyWith(
        status: AuthStatus.unauthenticated,
        isLoading: false,
        errorMessage: 'Unable to register account',
      );
      return false;
    }
  }

  Future<void> logout() async {
    await _repository.logout();
    state = state.copyWith(
      status: AuthStatus.unauthenticated,
      isLoading: false,
      errorMessage: null,
    );
  }

  Future<void> invalidateSession() async {
    await logout();
  }
}
