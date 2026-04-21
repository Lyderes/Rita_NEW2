import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';
import 'package:rita_mobile/features/alerts/data/state/alerts_state.dart';
import 'package:rita_mobile/shared/models/paginated_response.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

final alertsControllerProvider =
		StateNotifierProvider<AlertsController, AsyncValue<PaginatedResponse<AlertRead>>>(
	(ref) {
		final controller = AlertsController(ref.watch(alertsRepositoryProvider));
		controller.load();
		return controller;
	},
);
