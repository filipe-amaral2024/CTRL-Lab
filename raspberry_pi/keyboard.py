import logging
import os
import select
import sys
import threading

logger = logging.getLogger(__name__)


class KeyboardShortcutListener:
    """Recebe o atalho A do terminal sem bloquear o loop do Raspberry."""

    def __init__(self, callback):
        self.callback = callback
        self._stop_event = threading.Event()
        self._worker = None
        self._terminal_settings = None

    def start(self):
        if not sys.stdin.isatty():
            logger.info("Atalho de teclado indisponível: a entrada padrão não é um terminal.")
            return False
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError("O listener de teclado já está em execução.")

        if os.name != "nt":
            import termios
            import tty

            descriptor = sys.stdin.fileno()
            self._terminal_settings = (descriptor, termios.tcgetattr(descriptor))
            tty.setcbreak(descriptor)

        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._run,
            name="ctrlab-keyboard",
            daemon=True,
        )
        self._worker.start()
        logger.info("Atalho ativo: pressione A para alternar a verificação de acesso.")
        return True

    def stop(self):
        self._stop_event.set()
        if self._worker is not None:
            self._worker.join(timeout=1.0)
            if self._worker.is_alive():
                logger.warning("O listener de teclado ainda aguarda uma tecla.")
                return
            self._worker = None
        self._restore_terminal()

    def _run(self):
        while not self._stop_event.is_set():
            key = self._read_key()
            if key and key.lower() == "a":
                self.callback()

    def _read_key(self):
        if os.name == "nt":
            import msvcrt

            if msvcrt.kbhit():
                return msvcrt.getwch()
            self._stop_event.wait(0.05)
            return None

        ready, _, _ = select.select([sys.stdin], [], [], 0.1)
        return sys.stdin.read(1) if ready else None

    def _restore_terminal(self):
        if self._terminal_settings is None:
            return

        import termios

        descriptor, settings = self._terminal_settings
        termios.tcsetattr(descriptor, termios.TCSADRAIN, settings)
        self._terminal_settings = None
