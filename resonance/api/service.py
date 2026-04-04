"""Bounded application service for executing Resonance capabilities."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

from resonance.api.context import InvocationContext, InvocationMode
from resonance.errors import ValidationError, exit_code_for_exception
from resonance.api.output import OutputCollector


class ResonanceService:
    """Single bounded API surface for command execution."""

    def execute(
        self,
        args: Namespace,
        *,
        input_provider: Callable[[str], str] = input,
        output_sink: Callable[[str], None] = print,
    ) -> int:
        """Execute a parsed command namespace through the bounded API."""
        context = InvocationContext(
            mode=InvocationMode(getattr(args, "mode", "interactive")),
            json_output=getattr(args, "json", False),
        )
        return self.execute_namespace(
            args,
            context=context,
            input_provider=input_provider,
            output_sink=output_sink,
        )

    def execute_namespace(
        self,
        args: Namespace,
        *,
        context: InvocationContext,
        input_provider: Callable[[str], str] = input,
        output_sink: Callable[[str], None] = print,
    ) -> int:
        """Execute namespace under explicit invocation context."""
        self._validate_policy(args, context)

        command = getattr(args, "command", None)
        if command == "scan":
            return self._run_scan(args)
        if command == "app":
            return self._run_app(args, input_provider=input_provider, output_sink=output_sink)
        if command == "resolve":
            return self._run_resolve(args, output_sink=output_sink)
        if command == "prompt":
            return self._run_prompt(args, context=context, input_provider=input_provider)
        if command == "identify":
            return self._run_identify(args)
        if command == "plan":
            return self._run_plan(args)
        if command == "apply":
            return self._run_apply(args)
        if command == "decide":
            return self._run_decide(
                args,
                context=context,
                input_provider=input_provider,
                output_sink=output_sink,
            )
        if command == "audit":
            return self._run_audit(args, output_sink=output_sink)
        if command == "doctor":
            return self._run_doctor(args, output_sink=output_sink)
        if command == "rollback":
            return self._run_rollback(args, output_sink=output_sink)
        if command == "unjail":
            return self._run_unjail(args, output_sink=output_sink)

        raise ValidationError(f"Unsupported command: {command}")

    def _validate_policy(self, args: Namespace, context: InvocationContext) -> None:
        if context.mode in (InvocationMode.AUTOMATION, InvocationMode.ADMIN):
            if getattr(args, "command", None) == "prompt":
                if not getattr(args, "decisions_file", None) and not getattr(args, "replay_file", None):
                    raise ValidationError(
                        "prompt requires --decisions-file or --replay-file in automation/admin mode"
                    )

    def _run_scan(self, args: Namespace) -> int:
        from resonance.commands.scan import run_scan
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            return run_scan(args, store=store)
        finally:
            store.close()

    def _run_app(
        self,
        args: Namespace,
        *,
        input_provider: Callable[[str], str],
        output_sink: Callable[[str], None],
    ) -> int:
        from resonance.commands.app import run_app

        return run_app(
            args,
            service=self,
            input_provider=input_provider,
            output_sink=output_sink,
        )

    def _run_resolve(self, args: Namespace, *, output_sink: Callable[[str], None]) -> int:
        from resonance.commands.resolve import run_resolve
        from resonance.core.state import DirectoryState
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            collector = OutputCollector()
            code = run_resolve(
                args,
                store=store,
                auto_probable=getattr(args, "auto_probable", False),
                auto_probable_min_gap=getattr(args, "auto_probable_min_gap", 0.15),
                output_sink=collector.write,
            )
            for line in collector.lines:
                output_sink(line)

            if getattr(args, "mode", "interactive") in ("automation", "admin") and getattr(
                args, "fail_on_warning", False
            ):
                queued = len(store.list_by_state(DirectoryState.QUEUED_PROMPT))
                if queued > 0:
                    return 1
                if getattr(args, "json", False):
                    for line in reversed(collector.lines):
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        status = payload.get("data", {}).get("status")
                        if status in {"PARTIAL", "WARNING", "ERROR"}:
                            return 1
                        break
            return code
        finally:
            store.close()

    def _run_prompt(
        self,
        args: Namespace,
        *,
        context: InvocationContext,
        input_provider: Callable[[str], str],
    ) -> int:
        from resonance.commands.prompt import run_prompt
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            return run_prompt(args, store=store, input_provider=input_provider)
        finally:
            store.close()

    def _run_identify(self, args: Namespace) -> int:
        from resonance.commands.identify import run_identify

        cache_db = getattr(args, "cache_db", None)
        provider_client = None
        fingerprint_reader = None
        app = None
        if cache_db:
            from resonance.app import ResonanceApp

            app = ResonanceApp.from_env(
                library_root=Path(args.directory).resolve(),
                cache_path=cache_db,
            )
            provider_client = app.provider_client
            fingerprint_reader = app.fingerprint_reader

        if provider_client is None:
            import os

            acoustid_key = os.getenv("ACOUSTID_API_KEY")
            discogs_token = os.getenv("DISCOGS_TOKEN")
            if not acoustid_key and not discogs_token:
                raise ValidationError(
                    "No provider credentials configured. Set ACOUSTID_API_KEY or DISCOGS_TOKEN, or provide --cache-db."
                )

        try:
            return run_identify(
                args,
                provider_client=provider_client,
                fingerprint_reader=fingerprint_reader,
            )
        finally:
            if app is not None:
                app.close()

    def _run_plan(self, args: Namespace) -> int:
        if not args.state_db:
            raise ValidationError("state_db is required")

        from resonance.app import ResonanceApp
        from resonance.commands.plan import run_plan
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            provider_client = None
            cache_db = getattr(args, "cache_db", None)
            library_root = getattr(args, "library_root", None)
            app = None
            if cache_db and library_root:
                app = ResonanceApp.from_env(
                    library_root=Path(library_root).resolve(),
                    cache_path=cache_db,
                )
                provider_client = app.provider_client
            try:
                return run_plan(
                    args,
                    store=store,
                    provider_client=provider_client,
                    output_dir=getattr(args, "plan_dir", None),
                )
            finally:
                if app is not None:
                    app.close()
        finally:
            store.close()

    def _run_apply(self, args: Namespace) -> int:
        if not args.state_db:
            raise ValidationError("state_db is required")

        from resonance.commands.apply import run_apply
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            return run_apply(args, store=store)
        finally:
            store.close()

    def _run_decide(
        self,
        args: Namespace,
        *,
        context: InvocationContext,
        input_provider: Callable[[str], str],
        output_sink: Callable[[str], None],
    ) -> int:
        from resonance.commands.decide import run_decide
        from resonance.core.state import DirectoryState
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            provider_client = None
            app = None
            cache_db = getattr(args, "cache_db", None)
            if cache_db:
                from resonance.app import ResonanceApp

                offline = getattr(args, "offline", False)
                app = ResonanceApp.from_env(
                    library_root=Path(args.library_root).resolve(),
                    cache_path=cache_db,
                    offline=offline,
                )
                provider_client = app.provider_client
            if context.mode in (InvocationMode.AUTOMATION, InvocationMode.ADMIN):
                setattr(args, "headless", True)
            collector = OutputCollector()
            code = run_decide(
                args,
                store=store,
                provider_client=provider_client,
                input_provider=input_provider,
                output_sink=collector.write,
            )
            for line in collector.lines:
                output_sink(line)
            if (
                context.mode in (InvocationMode.AUTOMATION, InvocationMode.ADMIN)
                and getattr(args, "fail_on_prompt", False)
            ):
                queued = len(store.list_by_state(DirectoryState.QUEUED_PROMPT))
                if queued > 0:
                    return 1
            if (
                context.mode in (InvocationMode.AUTOMATION, InvocationMode.ADMIN)
                and getattr(args, "fail_on_warning", False)
            ):
                queued = len(store.list_by_state(DirectoryState.QUEUED_PROMPT))
                if queued > 0:
                    return 1
                if getattr(args, "json", False):
                    for line in reversed(collector.lines):
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        status = payload.get("data", {}).get("status")
                        if status in {"PARTIAL", "WARNING", "ERROR"}:
                            return 1
                        break
            return code
        finally:
            if "app" in locals() and app is not None:
                app.close()
            store.close()

    def _run_audit(self, args: Namespace, *, output_sink: Callable[[str], None]) -> int:
        import json

        from resonance.commands.audit import run_audit
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            result = run_audit(store=store, dir_id=args.dir_id)
            if getattr(args, "json", False):
                output_sink(json.dumps(result, default=str))
            else:
                for key, value in result.items():
                    output_sink(f"{key}: {value}")
            return 0
        finally:
            store.close()

    def _run_doctor(self, args: Namespace, *, output_sink: Callable[[str], None]) -> int:
        import json

        from resonance.commands.doctor import run_doctor
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            result = run_doctor(store=store, config_path=args.config)
            if getattr(args, "json", False):
                output_sink(json.dumps(result, default=str))
            else:
                issues = result.get("issues", [])
                if not issues:
                    output_sink("doctor: no issues found")
                else:
                    for issue in issues:
                        output_sink(f"doctor: {issue}")
            return 0
        finally:
            store.close()

    def _run_rollback(self, args: Namespace, *, output_sink: Callable[[str], None]) -> int:
        import json

        from resonance.commands.rollback import run_rollback

        if not args.report.exists():
            raise ValidationError(f"Report file not found: {args.report}")

        with open(args.report, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        file_ops = [SimpleNamespace(**op) for op in report_data.get("file_ops", [])]
        tag_ops = [SimpleNamespace(**op) for op in report_data.get("tag_ops", [])]
        report = SimpleNamespace(
            file_ops=file_ops,
            tag_ops=tag_ops,
            errors=report_data.get("errors", []),
        )

        result = run_rollback(
            report=report,
            source_dir=Path("."),
            destination_dir=Path("."),
            allowed_roots=(Path(args.library_root).resolve(),),
        )
        if getattr(args, "json", False):
            output_sink(json.dumps(result, default=str))
        else:
            output_sink(f"rollback: restored={result.get('restored', False)}")
        return 0

    def _run_unjail(self, args: Namespace, *, output_sink: Callable[[str], None]) -> int:
        from resonance.commands.unjail import run_unjail
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(args.state_db)
        try:
            run_unjail(store=store, dir_id=args.dir_id)
            output_sink(f"unjail: reset {args.dir_id} to NEW")
            return 0
        finally:
            store.close()


def execute_with_default_error_handling(
    service: ResonanceService,
    args: Namespace,
    *,
    input_provider: Callable[[str], str] = input,
    output_sink: Callable[[str], None] = print,
    error_sink: Callable[[str], None] = print,
) -> int:
    """Execute service call with stable CLI-style error handling."""
    try:
        return service.execute(args, input_provider=input_provider, output_sink=output_sink)
    except Exception as exc:  # pragma: no cover - exercised in CLI tests
        error_sink(str(exc))
        return exit_code_for_exception(exc)
