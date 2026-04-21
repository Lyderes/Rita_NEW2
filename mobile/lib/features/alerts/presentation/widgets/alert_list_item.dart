import 'package:flutter/material.dart';
import 'package:rita_mobile/core/utils/date_utils.dart';
import 'package:rita_mobile/features/alerts/data/models/alert_read.dart';
import 'package:rita_mobile/shared/widgets/operational_list_item_card.dart';

class AlertListItem extends StatelessWidget {
  const AlertListItem({
    required this.alert,
    this.onTap,
    super.key,
  });

  final AlertRead alert;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return OperationalListItemCard(
      title: alert.message,
      typeLabel: 'Type: ${alert.alertType}',
      severity: alert.severity,
      status: alert.status,
      timestampText: AppDateUtils.toShortDateTime(alert.createdAt),
      onTap: onTap,
    );
  }
}
