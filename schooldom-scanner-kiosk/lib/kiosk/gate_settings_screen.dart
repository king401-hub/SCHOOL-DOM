import 'package:flutter/material.dart';
import 'package:nfc_manager/nfc_manager.dart';
import '../api/gate_endpoints.dart';
import '../services/receipt_printer.dart';
import '../theme/app_theme.dart';

/// SchoolGate spec section 6 - Operating Mode, Attendance Schedule, and
/// Device status, gated behind an admin PIN. Reached from KioskHomeScreen's
/// status bar; there is still no other menu anywhere in the app.
class GateSettingsScreen extends StatefulWidget {
  const GateSettingsScreen({super.key});

  @override
  State<GateSettingsScreen> createState() => _GateSettingsScreenState();
}

class _GateSettingsScreenState extends State<GateSettingsScreen> {
  bool _loading = true;
  String? _error;
  String _mode = 'attendance_only';
  TimeOfDay _earlyStart = const TimeOfDay(hour: 7, minute: 30);
  TimeOfDay _earlyEnd = const TimeOfDay(hour: 8, minute: 30);
  TimeOfDay _lateStart = const TimeOfDay(hour: 8, minute: 31);
  TimeOfDay _lateEnd = const TimeOfDay(hour: 10, minute: 0);
  TimeOfDay _clockoutStart = const TimeOfDay(hour: 13, minute: 0);
  TimeOfDay _clockoutEnd = const TimeOfDay(hour: 16, minute: 0);
  int _duplicateSeconds = 30;
  bool _saving = false;

  bool? _nfcAvailable;
  bool? _printerAvailable;

  @override
  void initState() {
    super.initState();
    _load();
    _checkDeviceStatus();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await loadGateSettings();
      final data = res['data'] as Map<String, dynamic>;
      setState(() {
        _mode = data['mode'] as String? ?? 'attendance_only';
        _earlyStart = _parseTime(data['early_start']);
        _earlyEnd = _parseTime(data['early_end']);
        _lateStart = _parseTime(data['late_start']);
        _lateEnd = _parseTime(data['late_end']);
        _clockoutStart = _parseTime(data['clockout_start']);
        _clockoutEnd = _parseTime(data['clockout_end']);
        _duplicateSeconds = (data['duplicate_protection_seconds'] as num?)?.toInt() ?? 30;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _checkDeviceStatus() async {
    final nfc = await NfcManager.instance.isAvailable();
    final printer = await ReceiptPrinter.isAvailable();
    if (mounted) {
      setState(() {
        _nfcAvailable = nfc;
        _printerAvailable = printer;
      });
    }
  }

  TimeOfDay _parseTime(dynamic raw) {
    final text = (raw ?? '').toString();
    final parts = text.split(':');
    if (parts.length < 2) return const TimeOfDay(hour: 0, minute: 0);
    return TimeOfDay(hour: int.tryParse(parts[0]) ?? 0, minute: int.tryParse(parts[1]) ?? 0);
  }

  String _formatForApi(TimeOfDay t) =>
      '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  Future<void> _pickTime(TimeOfDay initial, ValueChanged<TimeOfDay> onPicked) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: initial,
      builder: (context, child) => Theme(
        data: Theme.of(context).copyWith(
          colorScheme: const ColorScheme.dark(primary: AppColors.primary, surface: Color(0xFF15213A)),
        ),
        child: child!,
      ),
    );
    if (picked != null) onPicked(picked);
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await updateGateSettings({
        'mode': _mode,
        'early_start': _formatForApi(_earlyStart),
        'early_end': _formatForApi(_earlyEnd),
        'late_start': _formatForApi(_lateStart),
        'late_end': _formatForApi(_lateEnd),
        'clockout_start': _formatForApi(_clockoutStart),
        'clockout_end': _formatForApi(_clockoutEnd),
        'duplicate_protection_seconds': _duplicateSeconds,
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Settings saved.'), backgroundColor: AppColors.success),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not save: $e'), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0B1220),
        elevation: 0,
        foregroundColor: Colors.white,
        title: const Text('Settings'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(_error!, style: const TextStyle(color: Colors.white70)),
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    _sectionLabel('Operating Mode'),
                    _card([
                      RadioListTile<String>(
                        value: 'attendance_only',
                        groupValue: _mode,
                        activeColor: AppColors.primary,
                        title: const Text('Attendance Only', style: TextStyle(color: Colors.white)),
                        onChanged: (v) => setState(() => _mode = v!),
                      ),
                      RadioListTile<String>(
                        value: 'fee_tracker',
                        groupValue: _mode,
                        activeColor: AppColors.primary,
                        title: const Text('Fee Tracker', style: TextStyle(color: Colors.white)),
                        onChanged: (v) => setState(() => _mode = v!),
                      ),
                    ]),
                    const SizedBox(height: 20),
                    _sectionLabel('Attendance Schedule'),
                    _card([
                      _timeRow('Early / Clock-in start', _earlyStart, (t) => setState(() => _earlyStart = t)),
                      _timeRow('Early / Clock-in end', _earlyEnd, (t) => setState(() => _earlyEnd = t)),
                      _timeRow('Late start', _lateStart, (t) => setState(() => _lateStart = t)),
                      _timeRow('Late end', _lateEnd, (t) => setState(() => _lateEnd = t)),
                      _timeRow('Clock-out start', _clockoutStart, (t) => setState(() => _clockoutStart = t)),
                      _timeRow('Clock-out end', _clockoutEnd, (t) => setState(() => _clockoutEnd = t)),
                    ]),
                    const SizedBox(height: 20),
                    _sectionLabel('Duplicate-Tap Protection'),
                    _card([
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                        child: Row(
                          children: [
                            const Expanded(
                              child: Text('Ignore repeat taps within (seconds)',
                                  style: TextStyle(color: Colors.white)),
                            ),
                            SizedBox(
                              width: 70,
                              child: TextFormField(
                                initialValue: _duplicateSeconds.toString(),
                                keyboardType: TextInputType.number,
                                textAlign: TextAlign.center,
                                style: const TextStyle(color: Colors.white),
                                decoration: const InputDecoration(border: OutlineInputBorder()),
                                onChanged: (v) => _duplicateSeconds = int.tryParse(v) ?? _duplicateSeconds,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 8),
                    ]),
                    const SizedBox(height: 20),
                    _sectionLabel('Device'),
                    _card([
                      _statusRow('Network', true, okLabel: 'Checked live on the home screen'),
                      _statusRow('NFC/RFID Reader', _nfcAvailable),
                      _statusRow('Thermal Printer', _printerAvailable),
                    ]),
                    const SizedBox(height: 24),
                    SizedBox(
                      width: double.infinity,
                      height: 50,
                      child: ElevatedButton(
                        onPressed: _saving ? null : _save,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: _saving
                            ? const SizedBox(
                                width: 22, height: 22,
                                child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5))
                            : const Text('Save Settings', style: TextStyle(fontWeight: FontWeight.bold)),
                      ),
                    ),
                  ],
                ),
    );
  }

  Widget _sectionLabel(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 8, left: 4),
        child: Text(text.toUpperCase(),
            style: const TextStyle(color: Colors.white54, fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: 0.6)),
      );

  Widget _card(List<Widget> children) => Container(
        decoration: BoxDecoration(color: const Color(0xFF15213A), borderRadius: BorderRadius.circular(16)),
        child: Column(mainAxisSize: MainAxisSize.min, children: children),
      );

  Widget _timeRow(String label, TimeOfDay value, ValueChanged<TimeOfDay> onChanged) {
    return ListTile(
      title: Text(label, style: const TextStyle(color: Colors.white)),
      trailing: Text(value.format(context), style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold)),
      onTap: () => _pickTime(value, onChanged),
    );
  }

  Widget _statusRow(String label, bool? ok, {String? okLabel}) {
    final color = ok == null ? Colors.white38 : (ok ? AppColors.success : AppColors.danger);
    final text = ok == null ? 'Checking...' : (okLabel ?? (ok ? 'Connected' : 'Not detected'));
    return ListTile(
      title: Text(label, style: const TextStyle(color: Colors.white)),
      trailing: Text(text, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12)),
    );
  }
}

/// Standalone PIN-entry gate shown before GateSettingsScreen - a bare numeric
/// keypad, matching spec section 6's "Settings should be protected by an
/// admin PIN/authentication."
class GatePinScreen extends StatefulWidget {
  const GatePinScreen({super.key});

  @override
  State<GatePinScreen> createState() => _GatePinScreenState();
}

class _GatePinScreenState extends State<GatePinScreen> {
  final _pinController = TextEditingController();
  bool _checking = false;
  String? _error;

  @override
  void dispose() {
    _pinController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _checking = true;
      _error = null;
    });
    try {
      final valid = await verifyGatePin(_pinController.text.trim());
      if (!mounted) return;
      if (valid) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const GateSettingsScreen()),
        );
      } else {
        setState(() => _error = 'Incorrect PIN.');
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.lock_outline, color: AppColors.primary, size: 48),
                const SizedBox(height: 16),
                const Text('Enter Admin PIN', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 20),
                TextField(
                  controller: _pinController,
                  obscureText: true,
                  keyboardType: TextInputType.number,
                  textAlign: TextAlign.center,
                  autofocus: true,
                  style: const TextStyle(color: Colors.white, fontSize: 24, letterSpacing: 8),
                  decoration: InputDecoration(
                    filled: true,
                    fillColor: const Color(0xFF15213A),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                  ),
                  onSubmitted: (_) => _submit(),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: AppColors.danger)),
                ],
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: ElevatedButton(
                    onPressed: _checking ? null : _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _checking
                        ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5))
                        : const Text('Continue', style: TextStyle(fontWeight: FontWeight.bold)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
