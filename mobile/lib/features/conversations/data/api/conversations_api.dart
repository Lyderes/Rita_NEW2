import 'package:rita_mobile/core/network/api_client.dart';
import 'package:rita_mobile/features/conversations/data/models/conversation_memory_read.dart';
import 'package:rita_mobile/features/conversations/data/models/conversation_session_read.dart';

class ConversationsApi {
  ConversationsApi(this._client);

  final ApiClient _client;

  Future<List<ConversationMemoryRead>> fetchMemories(int userId) async {
    final response = await _client.get(
      '/users/$userId/memories',
      queryParameters: {'active_only': true},
    );

    if (response is! List) {
      throw Exception('Invalid memories response');
    }

    return response
        .whereType<Map<String, dynamic>>()
        .map(ConversationMemoryRead.fromJson)
        .toList();
  }

  Future<List<ConversationSessionRead>> fetchSessions(int userId, {int limit = 20}) async {
    final response = await _client.get(
      '/users/$userId/conversations',
      queryParameters: {'limit': limit},
    );

    if (response is! List) {
      throw Exception('Invalid sessions response');
    }

    return response
        .whereType<Map<String, dynamic>>()
        .map(ConversationSessionRead.fromJson)
        .toList();
  }
}
