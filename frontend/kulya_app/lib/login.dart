import 'package:flutter/material.dart';

import 'state.dart';
import 'widgets.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen(this.state, {super.key});

  final AppState state;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _username = TextEditingController();
  final _password = TextEditingController();

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  void _submit() {
    if (_username.text.trim().isEmpty || _password.text.isEmpty || widget.state.busy) return;
    widget.state.login(_username.text.trim(), _password.text);
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    return Scaffold(
      body: Center(
        child: SizedBox(
          width: 420,
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    context.t.appTitle,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 40, fontWeight: FontWeight.w800, color: KColors.accent),
                  ),
                  Text(
                    context.t.appSubtitle,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: KColors.muted),
                  ),
                  const SizedBox(height: 24),
                  TextField(
                    controller: _username,
                    autofocus: true,
                    textDirection: TextDirection.ltr,
                    decoration: InputDecoration(labelText: context.t.username),
                    onSubmitted: (_) => _submit(),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _password,
                    obscureText: true,
                    textDirection: TextDirection.ltr,
                    decoration: InputDecoration(labelText: context.t.password),
                    onSubmitted: (_) => _submit(),
                  ),
                  const SizedBox(height: 18),
                  if (state.failure != null) ...[ErrorBanner(state), const SizedBox(height: 12)],
                  FilledButton(
                    onPressed: state.busy ? null : _submit,
                    child: state.busy
                        ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                        : Text(context.t.login),
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
