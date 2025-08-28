from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from dataclasses import dataclass

if TYPE_CHECKING:
    from core import TrayInputApp
    from core.logger_config import EnhancedLogger


class CallbackPosition(Enum):
    """
    Position of the callback in the main flow.
    """
    # Entire lifetime
    ON_LAUNCH = "on_launch"  # Program begins
    ON_EXIT = "on_exit"  # Program ends

    # Window activity
    ON_INPUT_BOX_SHOW = "on_input_box_show"  # Input box is shown
    ON_INPUT_BOX_HIDE = "on_input_box_hide"  # Input box is hidden (including `enter`, `escape`, `lose active`)
    ON_SETTINGS_SHOW = "on_settings_show"  # Settings are shown
    ON_SETTINGS_HIDE = "on_settings_hide"  # Settings are hidden (including save and cancel)
    
    # Input events
    ON_PASTE_IN_BOX = "on_paste_in_box"  # Text is pasted into the input box
    ON_TEXT_CHANGED = "on_text_changed"  # Text content changed in input box
    ON_ENTER_PRESSED = "on_enter_pressed"  # Enter key pressed in input box
    ON_ESCAPE_PRESSED = "on_escape_pressed"  # Escape key pressed in input box
    
    # System events
    ON_HOTKEY_TRIGGERED = "on_hotkey_triggered"  # Global hotkey triggered
    ON_FOCUS_GAINED = "on_focus_gained"  # Input box gained focus
    ON_FOCUS_LOST = "on_focus_lost"  # Input box lost focus


@dataclass
class CallbackContext:
    """
    Context information passed to callbacks.
    """
    app: Optional["TrayInputApp"]
    logger: "EnhancedLogger"
    data: dict[str, Any] | None = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}


@dataclass
class PluginMetadata:
    """
    Metadata for a plugin.
    """
    name: str
    version: str
    description: str
    author: str
    dependencies: list[str] | None = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class Callback(metaclass=ABCMeta):
    """
    Abstract base class for all callbacks.
    """

    @property
    @abstractmethod
    def position(self) -> CallbackPosition:
        """The position where this callback should be triggered."""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Priority of the callback (lower number = higher priority).
        Callbacks with the same position are executed in priority order.
        """
        pass

    @abstractmethod
    def __call__(self, context: CallbackContext) -> bool | None:
        """
        Execute the callback.
        
        Args:
            context: The callback context containing app, logger, and additional data
            
        Returns:
            bool | None: 
                - None or True: Continue processing other callbacks
                - False: Stop processing further callbacks for this position
        """
        pass

    @property
    def enabled(self) -> bool:
        """Whether this callback is enabled."""
        return True


@dataclass
class PluginSettings:
    """
    Plugin settings configuration.
    """
    display_name: str
    description: str = ""
    settings_widget_class: str | None = None  # Class name for custom settings widget
    config_schema: dict[str, Any] | None = None  # JSON Schema for config validation
    default_config: dict[str, Any] | None = None
    
    def __post_init__(self):
        if self.default_config is None:
            self.default_config = {}


class Plugin(metaclass=ABCMeta):
    """
    Abstract base class for all plugins.
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Metadata about this plugin."""
        pass

    @property
    @abstractmethod
    def callbacks(self) -> list[Callback]:
        """List of callbacks provided by this plugin."""
        pass

    @property
    def settings(self) -> PluginSettings | None:
        """
        Plugin settings configuration.
        Return None if plugin has no settings.
        """
        return None

    @property
    def settings_schema(self) -> dict[str, Any] | None:
        """
        Schema for plugin settings (JSON Schema format).
        Return None if plugin has no settings.
        DEPRECATED: Use settings.config_schema instead.
        """
        return None

    @property
    def default_settings(self) -> dict[str, Any]:
        """
        Default settings for this plugin.
        DEPRECATED: Use settings.default_config instead.
        """
        return {}

    def initialize(self, context: CallbackContext) -> bool:
        """
        Initialize the plugin.
        
        Args:
            context: The initialization context
            
        Returns:
            bool: True if initialization successful, False otherwise
        """
        return True

    def shutdown(self, context: CallbackContext) -> None:
        """
        Shutdown the plugin.
        
        Args:
            context: The shutdown context
        """
        pass

    @property
    def enabled(self) -> bool:
        """Whether this plugin is enabled."""
        return True

