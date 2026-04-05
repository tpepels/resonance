"""Bounded application service for executing Resonance capabilities."""

from __future__ import annotations

from argparse import Namespace
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Callable, Iterator

if TYPE_CHECKING:
    from resonance.infrastructure.directory_store import DirectoryStateStore

from resonance.api.context import InvocationContext, InvocationMode
from resonance.errors import ValidationError, exit_code_for_exception
from resonance.api.output import OutputCollector


class ResonanceService:
    """Single bounded API surface for command execution."""

    @contextmanager
    def _store_scope(self, state_db: Path) -> Iterator[DirectoryStateStore]:
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(state_db)
        try:
            yield store
        finally:
            store.close()

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

        command: str | None = getattr(args, "command", None)
        dispatch = {
            "scan": lambda: self._run_scan(args),
            "app": lambda: self._run_app(
                args,
                input_provider=input_provider,
                output_sink=output_sink,
            ),
            "resolve": lambda: self._run_resolve(args, output_sink=output_sink),
            "prompt": lambda: self._run_prompt(
                args,
                context=context,
                input_provider=input_provider,
            ),
            "identify": lambda: self._run_identify(args),
            "plan": lambda: self._run_plan(args),
            "apply": lambda: self._run_apply(args),
            "decide": lambda: self._run_decide(
                args,
                context=context,
                input_provider=input_provider,
                output_sink=output_sink,
            ),
            "audit": lambda: self._run_audit(args, output_sink=output_sink),
            "doctor": lambda: self._run_doctor(args, output_sink=output_sink),
            "rollback": lambda: self._run_rollback(args, output_sink=output_sink),
            "unjail": lambda: self._run_unjail(args, output_sink=output_sink),
            "stability": lambda: self._run_stability(args, output_sink=output_sink),
        }

        handler = dispatch.get(command) if command is not None else None
        if handler is not None:
            return handler()

        raise ValidationError(f"Unsupported command: {command}")
    def _run_stability(self, args: Namespace, output_sink) -> int:
        import json
        from resonance.commands.stability import run_stability_report
        try:
            with open(args.report_a, "r") as f:
                report_a = json.load(f)
            with open(args.report_b, "r") as f:
                report_b = json.load(f)
        except Exception as exc:
            output_sink(f"Error loading report files: {exc}")
            return 2
        result = run_stability_report(report_a, report_b)
        if getattr(args, "json", False):
            output_sink(json.dumps(result, indent=2))
        else:
            if result["same"]:
                output_sink("No differences detected.")
            else:
                output_sink("Differences detected:")
                for diff in result["differences"]:
                    output_sink(f"  Field: {diff['field']}\n    Left: {diff['left']}\n    Right: {diff['right']}")
        return 0

        handler = dispatch.get(command) if command is not None else None
        if handler is not None:
            return handler()

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

        with self._store_scope(args.state_db) as store:
            return run_scan(args, store=store)

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

        with self._store_scope(args.state_db) as store:
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

    def _run_prompt(
        self,
        args: Namespace,
        *,
        context: InvocationContext,
        input_provider: Callable[[str], str],
    ) -> int:
        from resonance.commands.prompt import run_prompt
        provider_client = None
        app = None
        cache_db = getattr(args, "cache_db", None)
        if cache_db:
            from resonance.app import ResonanceApp
            # Use library_root if available, else fallback to current dir
            library_root = getattr(args, "library_root", Path("."))
            app = ResonanceApp.from_env(
                library_root=Path(library_root).resolve(),
                cache_path=cache_db,
                offline=True,
            )
            provider_client = app.provider_client
        try:
            with self._store_scope(args.state_db) as store:
                return run_prompt(
                    args,
                    store=store,
                    provider_client=provider_client,
                    input_provider=input_provider,
                )
        finally:
            if app is not None:
                app.close()

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

        with self._store_scope(args.state_db) as store:
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

    def _run_apply(self, args: Namespace) -> int:
        if not args.state_db:
            raise ValidationError("state_db is required")

        from resonance.commands.apply import run_apply

        with self._store_scope(args.state_db) as store:
            return run_apply(args, store=store)

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

        with self._store_scope(args.state_db) as store:
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
            try:
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
                if context.mode in (InvocationMode.AUTOMATION, InvocationMode.ADMIN):
                    queued = len(store.list_by_state(DirectoryState.QUEUED_PROMPT))
                    if getattr(args, "fail_on_prompt", False) and queued > 0:
                        return 1
                    if getattr(args, "fail_on_warning", False):
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
                if app is not None:
                    app.close()

    def _run_audit(self, args: Namespace, *, output_sink: Callable[[str], None]) -> int:
        from resonance.commands.audit import run_audit

        with self._store_scope(args.state_db) as store:
            result = run_audit(store=store, dir_id=args.dir_id)
            if getattr(args, "json", False):
                output_sink(json.dumps(result, default=str))
            else:
                for key, value in result.items():
                    output_sink(f"{key}: {value}")
            return 0

    def _run_doctor(self, args: Namespace, *, output_sink: Callable[[str], None]) -> int:
        from resonance.commands.doctor import run_doctor

        with self._store_scope(args.state_db) as store:
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

    def _run_rollback(self, args: Namespace, *, output_sink: Callable[[str], None]) -> int:
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

        with self._store_scope(args.state_db) as store:
            run_unjail(store=store, dir_id=args.dir_id)
            output_sink(f"unjail: reset {args.dir_id} to NEW")
            return 0


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
