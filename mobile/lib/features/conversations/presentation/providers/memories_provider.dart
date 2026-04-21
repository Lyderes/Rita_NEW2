import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/conversations/data/models/conversation_memory_read.dart';
import 'package:rita_mobile/features/conversations/data/models/conversation_session_read.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

/// Fetches active memories for [userId]. Re-fetches on invalidation.
final AutoDisposeFutureProviderFamily<List<ConversationMemoryRead>, int>
    memoriesProvider = FutureProvider.autoDispose
        .family<List<ConversationMemoryRead>, int>((ref, userId) async {
  final api = ref.watch(conversationsApiProvider);
  return api.fetchMemories(userId);
});

/// Fetches recent conversation sessions for [userId].
final AutoDisposeFutureProviderFamily<List<ConversationSessionRead>, int>
    conversationSessionsProvider = FutureProvider.autoDispose
        .family<List<ConversationSessionRead>, int>((ref, userId) async {
  final api = ref.watch(conversationsApiProvider);
  return api.fetchSessions(userId);
});
