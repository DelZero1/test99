from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from typing import Any, Callable

from app.config import Settings


class PipelineExecutionError(Exception):
    pass


class RedditPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, reddit_url: str, job_id: str, result_dir: Path) -> None:
        if self.settings.pipeline_callable:
            self._run_callable(reddit_url, job_id, result_dir)
            return
        if self.settings.pipeline_command:
            self._run_command(reddit_url, job_id, result_dir)
            return
        raise PipelineExecutionError(
            "Nedostaje integracija pipelinea. Postavi REDDIT_PIPELINE_COMMAND ili REDDIT_PIPELINE_CALLABLE."
        )

    def _run_command(self, reddit_url: str, job_id: str, result_dir: Path) -> None:
        assert self.settings.pipeline_command is not None

        command = self.settings.pipeline_command.format(
            reddit_url=reddit_url,
            url=reddit_url,
            job_id=job_id,
            output_dir=str(result_dir),
            result_dir=str(result_dir),
        )

        completed = subprocess.run(
            command,
            shell=True,
            check=False,
            cwd=result_dir,
            capture_output=True,
            text=True,
        )

        if completed.returncode != 0:
            raise PipelineExecutionError(
                "Pipeline nije uspio. "
                f"stderr: {completed.stderr.strip() or '-'}; stdout: {completed.stdout.strip() or '-'}"
            )

    def _run_callable(self, reddit_url: str, job_id: str, result_dir: Path) -> None:
        assert self.settings.pipeline_callable is not None
        module_name, function_name = self.settings.pipeline_callable.split(":", maxsplit=1)
        module = importlib.import_module(module_name)
        function = getattr(module, function_name, None)
        if function is None or not callable(function):
            raise PipelineExecutionError(
                f"Pipeline callable nije pronađen: {self.settings.pipeline_callable}"
            )
        result = self._invoke_callable(function, reddit_url, job_id, result_dir)
        if result is False:
            raise PipelineExecutionError("Pipeline callable je vratio neuspjeh.")

    def _invoke_callable(
        self,
        function: Callable[..., Any],
        reddit_url: str,
        job_id: str,
        result_dir: Path,
    ) -> Any:
        try:
            return function(reddit_url=reddit_url, job_id=job_id, output_dir=result_dir)
        except TypeError:
            try:
                return function(reddit_url, job_id, result_dir)
            except TypeError as exc:
                raise PipelineExecutionError(
                    "Pipeline callable mora podržati potpis (reddit_url, job_id, output_dir)."
                ) from exc