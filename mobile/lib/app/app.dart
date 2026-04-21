import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/app/router.dart';
import 'package:rita_mobile/core/theme/app_theme.dart';
import 'package:rita_mobile/core/constants/routes.dart';
import 'package:rita_mobile/features/auth/data/state/auth_state.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';
import 'package:rita_mobile/shared/widgets/app_loader.dart';

class RitaApp extends ConsumerStatefulWidget {
  const RitaApp({super.key});

  @override
  ConsumerState<RitaApp> createState() => _RitaAppState();
}

class _RitaAppState extends ConsumerState<RitaApp> {
  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();
  StreamSubscription<RemoteMessage>? _fcmSub;
  OverlayEntry? _bannerEntry;

  @override
  void initState() {
    super.initState();
    _initFcmListener();
  }

  void _initFcmListener() {
    try {
      final service = ref.read(pushNotificationServiceProvider);
      service.listenForeground(_onForegroundMessage);
    } catch (_) {
      // Firebase not initialised — push notifications disabled
    }
  }

  void _onForegroundMessage(RemoteMessage message) {
    final title = message.notification?.title ?? 'Nueva alerta RITA';
    final body  = message.notification?.body  ?? '';
    _showBanner(title: title, body: body);
  }

  void _showBanner({required String title, required String body}) {
    _bannerEntry?.remove();
    _bannerEntry = null;

    final overlay = _navigatorKey.currentState?.overlay;
    if (overlay == null) return;

    late OverlayEntry entry;
    entry = OverlayEntry(
      builder: (_) => _NotificationBanner(
        title: title,
        body: body,
        onTap: () {
          entry.remove();
          _bannerEntry = null;
          _navigatorKey.currentState?.pushNamedAndRemoveUntil(
            AppRoutes.alerts,
            (r) => r.settings.name == AppRoutes.home,
          );
        },
        onDismiss: () {
          entry.remove();
          _bannerEntry = null;
        },
      ),
    );

    _bannerEntry = entry;
    overlay.insert(entry);

    // Auto-dismiss after 6 seconds
    Future.delayed(const Duration(seconds: 6), () {
      if (_bannerEntry == entry) {
        entry.remove();
        _bannerEntry = null;
      }
    });
  }

  @override
  void dispose() {
    _fcmSub?.cancel();
    _bannerEntry?.remove();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);

    ref.listen<AuthState>(authControllerProvider, (previous, next) {
      if (previous?.status == next.status) return;

      final navigator = _navigatorKey.currentState;
      if (navigator == null) return;

      if (next.status == AuthStatus.authenticated) {
        navigator.pushNamedAndRemoveUntil(AppRoutes.home, (route) => false);
        return;
      }
      if (next.status == AuthStatus.unauthenticated) {
        navigator.pushNamedAndRemoveUntil(AppRoutes.login, (route) => false);
      }
    });

    if (authState.status == AuthStatus.unknown) {
      return MaterialApp(
        key: const ValueKey<String>('rita-app-loading'),
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        home: const Scaffold(body: Center(child: AppLoader())),
      );
    }

    final initialRoute = authState.status == AuthStatus.authenticated
        ? AppRoutes.home
        : AppRoutes.login;

    return MaterialApp(
      key: const ValueKey<String>('rita-app-main'),
      debugShowCheckedModeBanner: false,
      title: 'RITA',
      theme: AppTheme.light,
      navigatorKey: _navigatorKey,
      routes: const <String, WidgetBuilder>{},
      onGenerateRoute: AppRouter.generateRoute,
      initialRoute: initialRoute,
    );
  }
}

// ---------------------------------------------------------------------------
// In-app notification banner
// ---------------------------------------------------------------------------

class _NotificationBanner extends StatefulWidget {
  const _NotificationBanner({
    required this.title,
    required this.body,
    required this.onTap,
    required this.onDismiss,
  });

  final String title;
  final String body;
  final VoidCallback onTap;
  final VoidCallback onDismiss;

  @override
  State<_NotificationBanner> createState() => _NotificationBannerState();
}

class _NotificationBannerState extends State<_NotificationBanner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<Offset> _slide;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _slide = Tween<Offset>(
      begin: const Offset(0, -1),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final topPadding = kIsWeb ? 16.0 : MediaQuery.of(context).padding.top + 8;

    return Positioned(
      top: topPadding,
      left: 16,
      right: 16,
      child: SlideTransition(
        position: _slide,
        child: Material(
          color: Colors.transparent,
          child: GestureDetector(
            onTap: widget.onTap,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              decoration: BoxDecoration(
                color: const Color(0xFF1A2332),
                borderRadius: BorderRadius.circular(14),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.25),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: const Color(0xFFE53935).withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.notifications_active_rounded,
                      color: Color(0xFFE53935),
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          widget.title,
                          style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                            fontSize: 14,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        if (widget.body.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            widget.body,
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.7),
                              fontSize: 13,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: widget.onTap,
                    style: TextButton.styleFrom(
                      foregroundColor: const Color(0xFF64B5F6),
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    child: const Text('Ver', style: TextStyle(fontWeight: FontWeight.w700)),
                  ),
                  IconButton(
                    onPressed: widget.onDismiss,
                    icon: Icon(Icons.close, color: Colors.white.withValues(alpha: 0.5), size: 18),
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
