import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/features/users/data/models/user_read.dart';
import 'package:rita_mobile/features/users/presentation/providers/users_provider.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';
import 'package:rita_mobile/shared/widgets/app_scaffold.dart';

class PersonaProfileEditScreen extends ConsumerStatefulWidget {
  const PersonaProfileEditScreen({required this.user, super.key});

  final UserRead user;

  @override
  ConsumerState<PersonaProfileEditScreen> createState() => _PersonaProfileEditScreenState();
}

class _PersonaProfileEditScreenState extends ConsumerState<PersonaProfileEditScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _nameController;
  late TextEditingController _notesController;
  bool _isLoading = false;
  String? _currentImageUrl;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.user.fullName);
    _notesController = TextEditingController(text: widget.user.notes);
    _currentImageUrl = widget.user.profileImageUrl;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  String _getAbsoluteUrl(String path) {
    if (path.startsWith('http')) return path;
    // In a real app, this would come from a proper config
    // For this environment, we use 127.0.0.1:8080 as defined in start-rita.ps1
    return 'http://127.0.0.1:8080$path';
  }

  Future<void> _pickAndUploadImage() async {
    final picker = ImagePicker();
    final image = await showModalBottomSheet<XFile?>(
      context: context,
      builder: (context) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library_rounded),
              title: const Text('Galería'),
              onTap: () async {
                final file = await picker.pickImage(source: ImageSource.gallery);
                Navigator.pop(context, file);
              },
            ),
            ListTile(
              leading: const Icon(Icons.camera_alt_rounded),
              title: const Text('Cámara'),
              onTap: () async {
                final file = await picker.pickImage(source: ImageSource.camera);
                Navigator.pop(context, file);
              },
            ),
          ],
        ),
      ),
    );

    if (image != null) {
      setState(() => _isLoading = true);
      try {
        await ref.read(usersControllerProvider.notifier).uploadUserPhoto(
              widget.user.id,
              image.path,
            );
        
        // Reload user to get new image URL
        final users = ref.read(usersControllerProvider).value;
        if (users != null) {
          final updatedUser = users.firstWhere((u) => u.id == widget.user.id);
          setState(() {
            _currentImageUrl = updatedUser.profileImageUrl;
          });
        }

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Foto actualizada correctamente')),
        );
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al subir la foto: $e')),
        );
      } finally {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      await ref.read(usersControllerProvider.notifier).updateUser(
            widget.user.id,
            fullName: _nameController.text.trim(),
            notes: _notesController.text.trim(),
          );
      if (mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Perfil actualizado correctamente')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al actualizar: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'Editar Perfil',
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: AppSpacing.md),
              Stack(
                children: [
                  CircleAvatar(
                    radius: 60,
                    backgroundColor: AppColors.surfaceVariant,
                    backgroundImage: _currentImageUrl != null
                        ? NetworkImage(_getAbsoluteUrl(_currentImageUrl!))
                        : null,
                    child: _currentImageUrl == null
                        ? const Icon(Icons.person_rounded, size: 60, color: AppColors.onSurfaceMuted)
                        : null,
                  ),
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: GestureDetector(
                      onTap: _pickAndUploadImage,
                      child: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: const BoxDecoration(
                          color: AppColors.primary,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.camera_alt_rounded, color: Colors.white, size: 20),
                      ),
                    ),
                  ),
                  if (_isLoading)
                    const Positioned.fill(
                      child: Center(child: CircularProgressIndicator()),
                    ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              TextButton(
                onPressed: _pickAndUploadImage,
                child: const Text('Cambiar Foto', style: TextStyle(fontWeight: FontWeight.w700)),
              ),
              const SizedBox(height: AppSpacing.xl),
              Align(
                alignment: Alignment.centerLeft,
                child: _buildSectionTitle('Información personal'),
              ),
              const SizedBox(height: AppSpacing.md),
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: 'Nombre completo',
                  hintText: 'Ej. Juan García',
                  prefixIcon: Icon(Icons.person_rounded),
                ),
                validator: (value) => 
                    value == null || value.isEmpty ? 'El nombre es obligatorio' : null,
              ),
              const SizedBox(height: AppSpacing.lg),
              Align(
                alignment: Alignment.centerLeft,
                child: _buildSectionTitle('Notas y descripción'),
              ),
              const SizedBox(height: AppSpacing.md),
              TextFormField(
                controller: _notesController,
                decoration: const InputDecoration(
                  labelText: 'Notas adicionales',
                  hintText: 'Ej. Preferencias, alergias o detalles importantes...',
                  prefixIcon: Icon(Icons.notes_rounded),
                  alignLabelWithHint: true,
                ),
                maxLines: 4,
              ),
              const SizedBox(height: AppSpacing.xl * 2),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _isLoading ? null : _save,
                  style: FilledButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  child: _isLoading 
                      ? const SizedBox(
                          height: 20, 
                          width: 20, 
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)
                        )
                      : const Text('Guardar cambios', style: TextStyle(fontWeight: FontWeight.w800)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: Theme.of(context).textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.w800,
            color: AppColors.onSurfaceMuted,
            letterSpacing: 0.5,
          ),
    );
  }
}
