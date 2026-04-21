import 'package:rita_mobile/core/errors/app_exception.dart';

class ApiError extends AppException {
  ApiError({
    required String message,
    this.code,
    this.error,
    this.requestId,
  }) : super(message);

  final int? code;
  final String? error;
  final String? requestId;
}
