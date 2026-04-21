import 'package:flutter/material.dart';
import 'package:rita_mobile/core/utils/date_utils.dart';
import 'package:rita_mobile/features/users/data/models/user_read.dart';

class UserListItem extends StatelessWidget {
  const UserListItem({
    required this.user,
    this.onTap,
    super.key,
  });

  final UserRead user;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        title: Text(user.fullName),
        subtitle: Text(
          user.birthDate != null
              ? 'Birth date: ${AppDateUtils.toShortDate(user.birthDate!)}'
              : 'Created: ${AppDateUtils.toShortDate(user.createdAt)}',
        ),
        onTap: onTap,
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (user.notes != null && user.notes!.isNotEmpty)
              const Icon(Icons.note_outlined),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }
}
