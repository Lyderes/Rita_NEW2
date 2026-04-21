import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';

class TimelineEventItem extends StatelessWidget {
  const TimelineEventItem({
    super.key,
    required this.title,
    required this.subtitle,
    this.eventType,
    this.leadingIcon,
    this.accentColor,
    this.onTap,
  });

  final String title;
  final String subtitle;
  final String? eventType;
  final IconData? leadingIcon;
  final Color? accentColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final Color tone = accentColor ?? AppColors.primary;
    final IconData icon = leadingIcon ?? _resolveIcon();

    return ListTile(
      dense: true,
      onTap: onTap,
      leading: CircleAvatar(
        radius: 18,
        backgroundColor: tone.withValues(alpha: 0.12),
        child: Icon(icon, size: 20, color: tone),
      ),
      title: Text(
        title,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        subtitle,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }

  IconData _resolveIcon() {
    switch (eventType?.trim().toLowerCase()) {
      case 'motion':
        return Icons.directions_walk_rounded;
      case 'sound':
      case 'assistant_response':
        return Icons.volume_up_rounded;
      case 'user_speech':
      case 'checkin':
        return Icons.record_voice_over_rounded;
      case 'heartbeat':
        return Icons.favorite_rounded;
      case 'alert':
      case 'emergency':
        return Icons.warning_amber_rounded;
      case 'command':
        return Icons.settings_remote_rounded;
      default:
        return Icons.circle;
    }
  }
}