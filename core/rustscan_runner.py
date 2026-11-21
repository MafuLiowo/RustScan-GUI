"""使用 QProcess 异步运行 rustscan，并聚合 stdout/stderr。"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from utils.paths import resolve_nmap


class RustscanRunner(QObject):
    """一次只运行一个 rustscan 进程。"""

    outputReceived = Signal(str)
    finished = Signal(int, str, str)
    failedToStart = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        nmap_path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._nmap_path = str(nmap_path) if nmap_path else ""
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._stdout_parts: list[str] = []
        self._stderr_parts: list[str] = []
        self._failure_reported = False

    def start(
        self,
        program: str | Path,
        arguments: list[str],
        working_directory: str | Path,
    ) -> None:
        self._stdout_parts.clear()
        self._stderr_parts.clear()
        self._failure_reported = False
        self._process.setProgram(str(program))
        self._process.setArguments(arguments)
        self._process.setWorkingDirectory(str(working_directory))
        environment = QProcessEnvironment.systemEnvironment()
        nmap = resolve_nmap(self._nmap_path)
        if nmap is not None:
            path_parts = environment.value("PATH").split(os.pathsep)
            nmap_dir = str(nmap.parent)
            if nmap_dir not in path_parts:
                path_parts.insert(0, nmap_dir)
            environment.insert("PATH", os.pathsep.join(part for part in path_parts if part))
        self._process.setProcessEnvironment(environment)
        self._process.start()

    def set_nmap_path(self, path: str | Path | None) -> None:
        """设置下一次扫描使用的 Nmap 可执行文件路径。"""
        self._nmap_path = str(path).strip().strip('"') if path else ""

    @property
    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def kill(self) -> None:
        if self.is_running:
            self._process.kill()
            self._process.waitForFinished(1500)

    def _read_stdout(self) -> None:
        chunk = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if chunk:
            self._stdout_parts.append(chunk)
            self.outputReceived.emit(chunk)

    def _read_stderr(self) -> None:
        chunk = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if chunk:
            self._stderr_parts.append(chunk)
            self.outputReceived.emit(chunk)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._read_stdout()
        self._read_stderr()
        if self._failure_reported:
            return
        self.finished.emit(
            int(exit_code),
            "".join(self._stdout_parts),
            "".join(self._stderr_parts),
        )

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._failure_reported = True
            self.failedToStart.emit(self._process.errorString())
