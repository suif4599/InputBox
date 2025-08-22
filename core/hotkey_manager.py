"""
Global hotkey manager with pluggable backends.
"""
import os
import asyncio
import threading
import traceback
from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any, Type
from .logger_config import get_logger

logger = get_logger(__name__)


class HotkeyManager(ABC):
    def __init__(self):
        self.callback: Optional[Callable] = None
        self.is_active = False
        
    @abstractmethod
    async def register_hotkey(self, hotkey: str, callback: Callable) -> bool:
        """Register a global hotkey with a callback function.
        
        Args:
            hotkey: Hotkey string (e.g., "Ctrl+Q")
            callback: Function to call when hotkey is pressed
            
        Returns:
            True if registration successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def unregister_hotkey(self) -> None:
        """Unregister the current hotkey."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the hotkey listener."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the hotkey listener."""
        pass
    
    @property
    def name(self) -> str:
        """Return the name of this hotkey manager implementation."""
        return self.__class__.__name__


class PynputHotkeyManager(HotkeyManager):
    def __init__(self):
        super().__init__()
        self.hotkey_listener = None
        self.hotkey_thread = None
        self.loop = None
        
    def _convert_qt_to_pynput_hotkey(self, qt_sequence: str) -> str:
        sequence_str = qt_sequence.lower()
        pynput_keys = []
        if 'ctrl' in sequence_str:
            pynput_keys.append('<ctrl>')
        if 'alt' in sequence_str:
            pynput_keys.append('<alt>')
        if 'shift' in sequence_str:
            pynput_keys.append('<shift>')
        main_key = sequence_str.split('+')[-1] if '+' in sequence_str else sequence_str
        main_key = main_key.strip()
        if main_key == 'space':
            pynput_keys.append('<space>')
        elif len(main_key) == 1:
            pynput_keys.append(main_key)
        else:
            pynput_keys.append(f'<{main_key}>')
        return '+'.join(pynput_keys)
    
    async def register_hotkey(self, hotkey: str, callback: Callable) -> bool:
        try:
            from pynput import keyboard
            await self.unregister_hotkey()
            self.callback = callback
            pynput_hotkey = self._convert_qt_to_pynput_hotkey(hotkey)
            def on_hotkey():
                if self.callback:
                    if asyncio.iscoroutinefunction(self.callback):
                        if self.loop and not self.loop.is_closed():
                            asyncio.run_coroutine_threadsafe(self.callback(), self.loop)
                    else:
                        self.callback()
            self.hotkey_listener = keyboard.GlobalHotKeys({
                pynput_hotkey: on_hotkey
            })
            logger.info(f"Registered pynput hotkey: {pynput_hotkey}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register pynput hotkey {hotkey}: {e}")
            return False
    
    async def unregister_hotkey(self) -> None:
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception as e:
                logger.warning(f"Error stopping pynput hotkey listener: {e}")
            self.hotkey_listener = None
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            try:
                self.hotkey_thread.join(timeout=1.0)
            except Exception as e:
                logger.warning(f"Error joining pynput hotkey thread: {e}")
            self.hotkey_thread = None
    
    async def start(self) -> None:
        if self.hotkey_listener and not self.is_active:
            self.loop = asyncio.get_event_loop()
            def run_listener():
                try:
                    if self.hotkey_listener:
                        self.hotkey_listener.start()
                except Exception as e:
                    logger.error(f"Error starting pynput hotkey listener: {e}")
            self.hotkey_thread = threading.Thread(target=run_listener, daemon=True)
            self.hotkey_thread.start()
            self.is_active = True
            logger.info("Started pynput hotkey listener")
    
    async def stop(self) -> None:
        if self.is_active:
            await self.unregister_hotkey()
            self.is_active = False
            logger.info("Stopped pynput hotkey listener")


class X11HotkeyManager(HotkeyManager):
    def __init__(self):
        super().__init__()
        self.registered_hotkey = None
        self.keybinder_available = False
        
        try:
            import gi
            gi.require_version('Keybinder', '3.0')
            from gi.repository import Keybinder # pyright: ignore[reportAttributeAccessIssue]
            Keybinder.init()
            self.keybinder_available = True
            logger.info("Keybinder initialized successfully")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Failed to initialize keybinder: {e}")
            self.keybinder_available = False
    
    def _convert_qt_to_keybinder_hotkey(self, qt_sequence: str) -> str:
        """Convert Qt hotkey sequence to keybinder format."""
        sequence_str = qt_sequence.lower()
        keybinder_keys = []
        if 'ctrl' in sequence_str:
            keybinder_keys.append('<Primary>')
        if 'alt' in sequence_str:
            keybinder_keys.append('<Alt>')  
        if 'shift' in sequence_str:
            keybinder_keys.append('<Shift>')
        main_key = sequence_str.split('+')[-1] if '+' in sequence_str else sequence_str
        main_key = main_key.strip()
        if main_key == 'space':
            keybinder_keys.append('space')
        elif len(main_key) == 1:
            keybinder_keys.append(main_key.lower())
        else:
            keybinder_keys.append(main_key.lower())
        
        return ''.join(keybinder_keys)
    
    async def register_hotkey(self, hotkey: str, callback: Callable) -> bool:
        if not self.keybinder_available:
            logger.error("Keybinder not available")
            return False
            
        try:
            import gi
            gi.require_version('Keybinder', '3.0')
            from gi.repository import Keybinder # pyright: ignore[reportAttributeAccessIssue]
            await self.unregister_hotkey()
            self.callback = callback
            keybinder_hotkey = self._convert_qt_to_keybinder_hotkey(hotkey)
            def on_hotkey(*args):
                if self.callback:
                    if asyncio.iscoroutinefunction(self.callback):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop and not loop.is_closed():
                                asyncio.create_task(self.callback())
                        except RuntimeError:
                            self.callback()
                    else:
                        self.callback()
            
            success = Keybinder.bind(keybinder_hotkey, on_hotkey)
            if success:
                self.registered_hotkey = keybinder_hotkey
                logger.info(f"Registered keybinder hotkey: {keybinder_hotkey}")
                return True
            else:
                logger.error(f"Failed to bind keybinder hotkey: {keybinder_hotkey}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to register keybinder hotkey {hotkey}: {e}")
            return False
    
    async def unregister_hotkey(self) -> None:
        if self.keybinder_available and self.registered_hotkey:
            try:
                import gi
                gi.require_version('Keybinder', '3.0')
                from gi.repository import Keybinder # pyright: ignore[reportAttributeAccessIssue]
                
                Keybinder.unbind(self.registered_hotkey)
                logger.info(f"Unregistered keybinder hotkey: {self.registered_hotkey}")
                self.registered_hotkey = None
            except Exception as e:
                logger.warning(f"Error unregistering keybinder hotkey: {e}")
    
    async def start(self) -> None:
        if self.keybinder_available and self.registered_hotkey:
            self.is_active = True
            logger.info("Started keybinder hotkey listener")
    
    async def stop(self) -> None:
        if self.is_active:
            await self.unregister_hotkey()
            self.is_active = False
            logger.info("Stopped keybinder hotkey listener")


def get_available_managers() -> Dict[str, Type[HotkeyManager]]:
    """Get dictionary of available hotkey managers."""
    managers: Dict[str, Type[HotkeyManager]] = {
        'pynput': PynputHotkeyManager,
    }
    
    # Check if keybinder is available
    try:
        if os.environ.get("XDG_SESSION_TYPE", "").strip().lower() != 'x11':
            raise RuntimeError("Not an X11 session")
        import gi
        gi.require_version('Keybinder', '3.0')
        from gi.repository import Keybinder # pyright: ignore[reportAttributeAccessIssue]
        managers['x11'] = X11HotkeyManager
        logger.info("Keybinder is available")
    except ImportError:
        logger.info("Keybinder libraries not available")
    except RuntimeError as re:
        logger.info(f"Keybinder not available: {re}")
    except Exception as e:
        logger.info(f"Keybinder not available: {e}")
    
    return managers




def get_auto_manager_name() -> str:
    """Get the name of the manager that would be selected in auto mode.
    
    Returns:
        Name of the auto-selected manager (e.g., 'pynput', 'x11')
    """
    available = get_available_managers()

    if 'x11' in available:
        return 'x11'
    elif 'pynput' in available:
        return 'pynput'
    return 'unknown'


def get_manager_display_name(manager_name: str) -> str:
    """Get display name for a manager.
    
    Args:
        manager_name: Internal manager name ('pynput', 'x11', etc.)
        
    Returns:
        User-friendly display name
    """
    name_map = {
        'pynput': 'Pynput',
        'x11': 'X11 Keybinder',
        'unknown': 'Unknown'
    }
    return name_map.get(manager_name, manager_name.title())


def create_hotkey_manager(preferred: str = 'auto') -> HotkeyManager:
    """Create the best available hotkey manager.
    
    Args:
        preferred: Preferred manager type ('auto', 'x11', 'pynput')
        
    Returns:
        HotkeyManager instance
    """
    available = get_available_managers()
    
    if preferred == 'auto':
        preferred = get_auto_manager_name()

    if preferred in available:
        logger.info(f"Using {preferred} hotkey manager")
        return available[preferred]()
    else:
        raise ValueError(f"Hotkey manager '{preferred}' not available. Available: {list(available.keys())}")
