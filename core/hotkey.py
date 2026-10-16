"""
core/hotkey.py
==============
Global hotkey listener for Windows using ctypes RegisterHotKey.
Runs a background QThread with a Windows message loop to capture hotkeys
even when Taskmaster is minimized, hidden in tray, or out of focus.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

HOTKEY_ID_VOICE = 101

# Virtual Key Codes
VK_SPACE = 0x20
VK_V = 0x56
VK_T = 0x54


class GlobalHotkeyListener(QThread):
    """
    Listens for Windows global hotkeys in a lightweight background thread.
    Emits hotkey_triggered when the registered combination is pressed.
    """

    hotkey_triggered = pyqtSignal()

    def __init__(
        self,
        modifiers: int = MOD_CONTROL | MOD_ALT,
        vk_code: int = VK_SPACE,
        parent: Optional[object] = None,
    ):
        super().__init__(parent)
        self.modifiers = modifiers | MOD_NOREPEAT
        self.vk_code = vk_code
        self._thread_id: Optional[int] = None
        self._is_registered = False

    def run(self) -> None:
        """Windows thread message pump."""
        try:
            import ctypes
            import ctypes.wintypes
        except ImportError:
            logger.warning("ctypes not available; global hotkey disabled.")
            return

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        self._thread_id = kernel32.GetCurrentThreadId()

        # Register hotkey on thread message queue (hWnd=None)
        success = user32.RegisterHotKey(
            None,
            HOTKEY_ID_VOICE,
            self.modifiers,
            self.vk_code,
        )

        if not success:
            logger.warning(
                "Could not register global hotkey (modifiers=%s, vk=%s). It may already be registered by another app.",
                self.modifiers,
                self.vk_code,
            )
            return

        self._is_registered = True
        logger.info(
            "Global hotkey registered successfully (Ctrl+Alt+Space, ID=%d).",
            HOTKEY_ID_VOICE,
        )

        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_VOICE:
                logger.debug("Global voice hotkey triggered!")
                self.hotkey_triggered.emit()

        if self._is_registered:
            user32.UnregisterHotKey(None, HOTKEY_ID_VOICE)
            self._is_registered = False
            logger.info("Global hotkey unregistered.")

    def stop(self) -> None:
        """Signal thread to exit message loop and unregister hotkey."""
        if self._thread_id:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception as exc:
                logger.debug("Error posting WM_QUIT to hotkey thread: %s", exc)
        self.wait(1500)
