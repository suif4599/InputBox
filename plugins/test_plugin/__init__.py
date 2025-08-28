import sys
import os

# Add parent directory to path to import interface
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from interface import Plugin, Callback, CallbackPosition, CallbackContext, PluginMetadata, PluginSettings
from typing import List, Optional


class TestCallback(Callback):
    """Test callback that logs all events."""
    
    def __init__(self, position: CallbackPosition, priority: int = 100):
        self._position = position
        self._priority = priority
    
    @property
    def position(self) -> CallbackPosition:
        return self._position
    
    @property
    def priority(self) -> int:
        return self._priority
    
    def __call__(self, context: CallbackContext) -> bool | None:
        if context.logger:
            context.logger.info(f"[TestPlugin] Triggered callback for {self.position.value}")
        return None  # Continue processing other callbacks


class TestPlugin(Plugin):
    """Simple test plugin."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Test Plugin",
            version="1.0.0",
            description="A simple test plugin to verify the plugin system",
            author="System Test"
        )
    
    @property
    def settings(self) -> PluginSettings | None:
        return PluginSettings(
            display_name="Test Plugin Settings",
            description="Configuration options for the test plugin",
            default_config={
                "log_callbacks": True,
                "priority_offset": 0,
                "enabled_positions": ["on_launch", "on_exit", "on_input_box_show"]
            }
        )
    
    @property
    def callbacks(self) -> list[Callback]:
        # Create callbacks for various positions
        return [
            TestCallback(CallbackPosition.ON_LAUNCH),
            TestCallback(CallbackPosition.ON_EXIT),
            TestCallback(CallbackPosition.ON_INPUT_BOX_SHOW),
            TestCallback(CallbackPosition.ON_INPUT_BOX_HIDE),
            TestCallback(CallbackPosition.ON_HOTKEY_TRIGGERED),
            TestCallback(CallbackPosition.ON_PASTE_IN_BOX),
            TestCallback(CallbackPosition.ON_TEXT_CHANGED, priority=50),  # Higher priority
        ]
    
    def initialize(self, context: CallbackContext) -> bool:
        if context.logger:
            context.logger.info("[TestPlugin] Initializing test plugin")
        return True
    
    def shutdown(self, context: CallbackContext) -> None:
        if context.logger:
            context.logger.info("[TestPlugin] Shutting down test plugin")


# Plugin factory function
def create_plugin() -> Plugin:
    return TestPlugin()
