import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Exposes the current connectivity state as a [StreamProvider].
///
/// `true`  = at least one network interface is available (wifi, mobile, ethernet)
/// `false` = no network (none)
///
/// Usage:
///   final isOnline = ref.watch(connectivityProvider).valueOrNull ?? true;
final StreamProvider<bool> connectivityProvider = StreamProvider<bool>((ref) {
  return Connectivity()
      .onConnectivityChanged
      .map((results) => results.any((r) => r != ConnectivityResult.none));
});
