import 'package:flutter_test/flutter_test.dart';
import 'package:rita_mobile/core/errors/api_error.dart';
import 'package:rita_mobile/features/auth/data/models/token_response.dart';
import 'package:rita_mobile/features/auth/data/repository/auth_repository.dart';
import 'package:rita_mobile/features/auth/data/state/auth_state.dart';
import 'package:rita_mobile/features/auth/presentation/providers/auth_provider.dart';

class _FakeAuthRepository implements AuthRepository {
  _FakeAuthRepository({
    this.hasSessionValue = false,
    this.loginShouldFail = false,
    this.registerShouldFail = false,
  });

  bool hasSessionValue;
  bool loginShouldFail;
  bool registerShouldFail;
  bool logoutCalled = false;

  @override
  Future<bool> hasSession() async => hasSessionValue;

  @override
  Future<TokenResponse> login({
    required String username,
    required String password,
  }) async {
    if (loginShouldFail) {
      throw ApiError(message: 'invalid credentials', code: 401);
    }
    return TokenResponse(accessToken: 'token-login', tokenType: 'bearer');
  }

  @override
  Future<void> logout() async {
    logoutCalled = true;
  }

  @override
  Future<TokenResponse> register({
    required String username,
    required String password,
    String? fullName,
  }) async {
    if (registerShouldFail) {
      throw ApiError(message: 'username exists', code: 409);
    }
    return TokenResponse(accessToken: 'token-register', tokenType: 'bearer');
  }
}

void main() {
  group('AuthController', () {
    test('bootstrap leaves authenticated when session token exists', () async {
      final repository = _FakeAuthRepository(hasSessionValue: true);
      final controller = AuthController(repository);

      await controller.bootstrap();

      expect(controller.state.status, AuthStatus.authenticated);
      expect(controller.state.errorMessage, isNull);
    });

    test('register authenticates user on success', () async {
      final repository = _FakeAuthRepository();
      final controller = AuthController(repository);

      final ok = await controller.register(
        username: 'new_user',
        password: 'Secret123!',
        fullName: 'New User',
      );

      expect(ok, isTrue);
      expect(controller.state.status, AuthStatus.authenticated);
      expect(controller.state.isLoading, isFalse);
    });

    test('login error keeps user unauthenticated with message', () async {
      final repository = _FakeAuthRepository(loginShouldFail: true);
      final controller = AuthController(repository);

      final ok = await controller.login(username: 'user', password: 'bad');

      expect(ok, isFalse);
      expect(controller.state.status, AuthStatus.unauthenticated);
      expect(controller.state.errorMessage, 'invalid credentials');
    });

    test('register error keeps user unauthenticated with message', () async {
      final repository = _FakeAuthRepository(registerShouldFail: true);
      final controller = AuthController(repository);

      final ok = await controller.register(
        username: 'existing_user',
        password: 'Secret123!',
      );

      expect(ok, isFalse);
      expect(controller.state.status, AuthStatus.unauthenticated);
      expect(
        controller.state.errorMessage,
        'Ese usuario ya existe. Inicia sesion o usa otro nombre de usuario.',
      );
    });

    test('logout clears session state', () async {
      final repository = _FakeAuthRepository();
      final controller = AuthController(repository)
        ..state = const AuthState(status: AuthStatus.authenticated);

      await controller.logout();

      expect(repository.logoutCalled, isTrue);
      expect(controller.state.status, AuthStatus.unauthenticated);
      expect(controller.state.errorMessage, isNull);
    });
  });
}
