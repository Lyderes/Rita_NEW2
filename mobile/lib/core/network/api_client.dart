import 'package:dio/dio.dart';
import 'package:rita_mobile/core/errors/api_error.dart';
import 'package:rita_mobile/core/network/auth_interceptor.dart';
import 'package:rita_mobile/core/network/request_logger.dart';
import 'package:rita_mobile/core/network/retry_interceptor.dart';
import 'package:rita_mobile/core/storage/secure_storage_service.dart';
import 'package:rita_mobile/shared/models/api_error_response.dart';

class ApiClient {
  ApiClient({
    required String baseUrl,
    required SecureStorageService secureStorage,
    void Function()? onUnauthorized,
  }) : _dio = Dio(
          BaseOptions(
            baseUrl: baseUrl,
            contentType: Headers.jsonContentType,
            connectTimeout: const Duration(seconds: 30),
            receiveTimeout: const Duration(seconds: 30),
          ),
        ) {
    _dio.interceptors.addAll([
      RetryInterceptor(dio: _dio),
      AuthInterceptor(
        secureStorage: secureStorage,
        onUnauthorized: onUnauthorized,
      ),
      RequestLoggerInterceptor(),
    ]);
  }

  final Dio _dio;
  Dio get dio => _dio;

  Future<dynamic> get(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.get<dynamic>(
        path,
        queryParameters: queryParameters,
      );
      return response.data;
    } on DioException catch (error) {
      throw _toApiError(error);
    }
  }

  Future<dynamic> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.post<dynamic>(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return response.data;
    } on DioException catch (error) {
      throw _toApiError(error);
    }
  }

  Future<dynamic> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.patch<dynamic>(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return response.data;
    } on DioException catch (error) {
      throw _toApiError(error);
    }
  }

  Future<dynamic> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.put<dynamic>(
        path,
        data: data,
        queryParameters: queryParameters,
      );
      return response.data;
    } on DioException catch (error) {
      throw _toApiError(error);
    }
  }

  Future<dynamic> delete(String path) async {
    try {
      final response = await _dio.delete<dynamic>(path);
      return response.data;
    } on DioException catch (error) {
      throw _toApiError(error);
    }
  }

  ApiError _toApiError(DioException error) {
    final payload = error.response?.data;
    if (payload is Map<String, dynamic>) {
      final apiError = ApiErrorResponse.fromJson(payload);
      return ApiError(
        message: apiError.message,
        code: apiError.code == 0 ? error.response?.statusCode : apiError.code,
        error: apiError.error,
        requestId: apiError.requestId,
      );
    }

    return ApiError(
      message: error.response == null
          ? 'Network error: cannot reach backend. Verify API URL/CORS and backend availability.'
          : (error.message ?? 'Request failed'),
      code: error.response?.statusCode,
    );
  }
}
