import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:rita_mobile/app/app.dart';

void main() {
  testWidgets('RitaApp builds', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: RitaApp()));
    await tester.pump();
    expect(find.byType(RitaApp), findsOneWidget);
  });
}
