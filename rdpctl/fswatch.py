"""Dosya değişikliği izleyici.

Bağlı kullanıcı kontrol ederken, izlenen klasörlerdeki dosya
oluşturma/değiştirme/silme/taşıma olaylarını denetim günlüğüne yazar.
Böylece "bağlanılan bilgisayarda yapılan değişikliklerin logu" tutulur.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class _Handler(FileSystemEventHandler):
    def __init__(self, sink: Callable[[str, str], None]):
        self._sink = sink

    def _emit(self, kind: str, event: FileSystemEvent) -> None:
        if event.is_directory and kind == "modified":
            return  # dizin "modified" gürültüsünü ele
        path = getattr(event, "dest_path", "") or event.src_path
        self._sink(kind, path)

    def on_created(self, event): self._emit("created", event)
    def on_deleted(self, event): self._emit("deleted", event)
    def on_modified(self, event): self._emit("modified", event)
    def on_moved(self, event): self._emit("moved", event)


class FileChangeWatcher:
    def __init__(self, paths: List[str], sink: Callable[[str, str], None]):
        self._paths = paths
        self._sink = sink
        self._observer: Optional[Observer] = None

    def start(self) -> None:
        if self._observer is not None:
            return
        self._observer = Observer()
        handler = _Handler(self._sink)
        for p in self._paths:
            try:
                self._observer.schedule(handler, p, recursive=True)
            except (FileNotFoundError, OSError):
                continue
        self._observer.daemon = True
        self._observer.start()

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            try:
                self._observer.join(timeout=3)
            except RuntimeError:
                pass
            self._observer = None
