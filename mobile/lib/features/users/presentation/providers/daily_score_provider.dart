
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/users/data/models/daily_score.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

final dailyScoreProvider = FutureProvider.family<DailyScore, int>((ref, userId) async {
  final api = ref.watch(usersApiProvider);
  return api.fetchLatestDailyScore(userId);
});
