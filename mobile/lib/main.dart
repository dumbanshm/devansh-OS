import 'package:flutter/material.dart';

import 'screens/quick_log_screen.dart';
import 'screens/sign_in_screen.dart';
import 'supabase_client.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initSupabase();
  runApp(const DevanshOSApp());
}

class DevanshOSApp extends StatelessWidget {
  const DevanshOSApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Devansh OS',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0B0E14),
        colorSchemeSeed: const Color(0xFF22D3EE),
        useMaterial3: true,
      ),
      home: supabase.auth.currentSession == null
          ? const SignInScreen()
          : const QuickLogScreen(),
    );
  }
}
