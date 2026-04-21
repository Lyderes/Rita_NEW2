import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/constants/routes.dart';
import 'package:rita_mobile/core/services/connectivity_service.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/features/alerts/presentation/providers/alerts_provider.dart';
import 'package:rita_mobile/features/caregiver/presentation/providers/caregiver_context_provider.dart';

class AppScaffold extends ConsumerWidget {
  const AppScaffold({
    required this.title,
    required this.body,
    this.actions,
    super.key,
  });

  final String title;
  final Widget body;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentRoute = ModalRoute.of(context)?.settings.name;
    final caregiverIndex = _caregiverTabIndex(currentRoute);
    final showCaregiverNav = caregiverIndex >= 0;

    final alertsState = ref.watch(alertsControllerProvider);
    final pendingCount = alertsState.maybeWhen(
      data: (result) => result.items.where((a) => a.status.toLowerCase() == 'pending').length,
      orElse: () => 0,
    );

    final activeUser = ref.watch(caregiverActiveUserProvider);

    final isOnline = ref.watch(connectivityProvider).valueOrNull ?? true;

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: actions,
        centerTitle: true,
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: AppColors.appBackgroundGradient,
        ),
        child: Column(
          children: <Widget>[
            if (!isOnline) const _OfflineBanner(),
            Expanded(child: body),
          ],
        ),
      ),
      bottomNavigationBar: showCaregiverNav
          ? NavigationBar(
              selectedIndex: caregiverIndex,
              onDestinationSelected: (int index) {
                if (index == 0) {
                  Navigator.of(context).pushReplacementNamed(AppRoutes.home);
                } else if (index == 1) {
                  Navigator.of(context).pushReplacementNamed(AppRoutes.alerts);
                } else if (index == 2) {
                  Navigator.of(context).pushReplacementNamed(AppRoutes.history);
                } else if (index == 3) {
                  if (activeUser != null) {
                    Navigator.of(context).pushReplacementNamed(
                      AppRoutes.userDetail,
                      arguments: activeUser.id,
                    );
                  } else {
                    Navigator.of(context).pushReplacementNamed(AppRoutes.profile);
                  }
                }
              },
              destinations: <NavigationDestination>[
                const NavigationDestination(
                  icon: Icon(Icons.home_outlined),
                  selectedIcon: Icon(Icons.home_rounded),
                  label: 'Inicio',
                ),
                NavigationDestination(
                  icon: Badge(
                    label: Text('$pendingCount'),
                    isLabelVisible: pendingCount > 0,
                    child: const Icon(Icons.notifications_outlined),
                  ),
                  selectedIcon: Badge(
                    label: Text('$pendingCount'),
                    isLabelVisible: pendingCount > 0,
                    child: const Icon(Icons.notifications_rounded),
                  ),
                  label: 'Alertas',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.bar_chart_rounded),
                  selectedIcon: Icon(Icons.bar_chart_rounded),
                  label: 'Historial',
                ),
                const NavigationDestination(
                  icon: Icon(Icons.person_outline_rounded),
                  selectedIcon: Icon(Icons.person_rounded),
                  label: 'Persona',
                ),
              ],
            )
          : null,
    );
  }

  int _caregiverTabIndex(String? route) {
    if (route == AppRoutes.home) {
      return 0;
    }
    if (_routeIn(route, <String>{AppRoutes.alerts, AppRoutes.alertDetail})) {
      return 1;
    }
    if (route == AppRoutes.history) {
      return 2;
    }
    if (_routeIn(route, <String>{AppRoutes.profile, AppRoutes.userDetail})) {
      return 3;
    }
    return -1;
  }

  bool _routeIn(String? route, Set<String> allowedRoutes) {
    if (route == null) {
      return false;
    }
    return allowedRoutes.contains(route);
  }
}

class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
      color: AppColors.warning,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: const <Widget>[
          Icon(Icons.wifi_off_rounded, size: 16, color: Colors.white),
          SizedBox(width: 8),
          Text(
            'Sin conexión — los datos pueden no estar actualizados',
            style: TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
