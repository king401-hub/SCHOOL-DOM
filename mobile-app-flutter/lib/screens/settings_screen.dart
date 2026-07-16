import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import 'package:provider/provider.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/app_screen.dart';
import '../widgets/primary_button.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  Future<void> _enableBiometrics(BuildContext context) async {
    await context.read<AuthProvider>().enableBiometrics(true);
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Biometric unlock enabled.')),
      );
    }
  }

  Future<void> _openCamera(BuildContext context) async {
    try {
      final picker = ImagePicker();
      await picker.pickImage(source: ImageSource.camera);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString())),
        );
      }
    }
  }

  Future<void> _pickFile(BuildContext context) async {
    try {
      await FilePicker.platform.pickFiles();
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString())),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return AppScreen(
      children: [
        const Text(
          'Settings',
          style: TextStyle(
              color: AppColors.text,
              fontSize: 28,
              fontWeight: FontWeight.w900),
        ),
        AppCard(
          children: [
            const Text(
              'Account',
              style: TextStyle(
                  color: AppColors.textDark,
                  fontSize: 16,
                  fontWeight: FontWeight.w900),
            ),
            if (auth.displayName != null)
              Text(auth.displayName!,
                  style: const TextStyle(color: AppColors.mutedDark)),
            if (auth.role != null)
              Text(auth.role!.toUpperCase(),
                  style: const TextStyle(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w800,
                      fontSize: 12)),
          ],
        ),
        AppCard(
          children: [
            const Text(
              'Device services',
              style: TextStyle(
                  color: AppColors.textDark,
                  fontSize: 16,
                  fontWeight: FontWeight.w900),
            ),
            PrimaryButton(
              title: 'Enable biometric unlock',
              onPressed: () => _enableBiometrics(context),
            ),
            PrimaryButton(
              title: 'Open camera',
              tone: ButtonTone.ghost,
              onPressed: () => _openCamera(context),
            ),
            PrimaryButton(
              title: 'Pick file',
              tone: ButtonTone.ghost,
              onPressed: () => _pickFile(context),
            ),
          ],
        ),
        PrimaryButton(
          title: 'Sign out',
          tone: ButtonTone.danger,
          onPressed: () => auth.signOut(),
        ),
      ],
    );
  }
}
