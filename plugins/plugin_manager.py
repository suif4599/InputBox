import sys
import importlib
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any

from interface import Plugin, Callback, CallbackPosition, CallbackContext

if TYPE_CHECKING:
    from core.logger_config import EnhancedLogger


class PluginManager:
    """
    Manages loading, initialization, and execution of plugins.
    """
    
    def __init__(self, plugins_dir: str, logger: "EnhancedLogger"):
        self.plugins_dir = Path(plugins_dir)
        self.logger = logger
        self.plugins: list[Plugin] = []
        self.callbacks: dict[CallbackPosition, list[Callback]] = {
            position: [] for position in CallbackPosition
        }
        self._last_known_directories: set[str] = set()
    
    def load_plugins(self) -> None:
        """
        Load all plugins from the plugins directory.
        """
        self.logger.info(f"Loading plugins from {self.plugins_dir}")
        
        if not self.plugins_dir.exists():
            self.logger.warning(f"Plugins directory {self.plugins_dir} does not exist")
            return
        self.plugins.clear()
        for position in CallbackPosition:
            self.callbacks[position].clear()
        plugin_dirs = [d for d in self.plugins_dir.iterdir() 
                      if d.is_dir() and not d.name.startswith('__')]
        
        current_directories = {d.name for d in plugin_dirs}
        if self._last_known_directories:
            new_plugins = current_directories - self._last_known_directories
            for new_plugin_name in new_plugins:
                if not new_plugin_name.endswith('.disabled'):
                    old_path = self.plugins_dir / new_plugin_name
                    new_path = self.plugins_dir / f"{new_plugin_name}.disabled"
                    try:
                        old_path.rename(new_path)
                        self.logger.info(f"Auto-disabled new plugin: {new_plugin_name}")
                    except Exception as e:
                        self.logger.error(f"Failed to auto-disable new plugin {new_plugin_name}: {e}")
        
        self._last_known_directories = current_directories.copy()
        plugin_dirs = [d for d in self.plugins_dir.iterdir() 
                      if d.is_dir() and not d.name.startswith('__')]
        for plugin_dir in plugin_dirs:
            self._load_plugin(plugin_dir)
        
        for position in CallbackPosition:
            self.callbacks[position].sort(key=lambda cb: cb.priority)
        self.logger.info(f"Loaded {len(self.plugins)} plugins")
    
    def _load_plugin(self, plugin_dir: Path) -> None:
        """
        Load a single plugin from a directory.
        """
        plugin_name = plugin_dir.name
        
        is_disabled = plugin_name.endswith('.disabled')
        if is_disabled:
            actual_name = plugin_name[:-9]
        else:
            actual_name = plugin_name
        
        try:
            init_file = plugin_dir / "__init__.py"
            main_file = plugin_dir / "main.py"
            
            if init_file.exists():
                module_file = init_file
            elif main_file.exists():
                module_file = main_file
            else:
                self.logger.warning(f"No entry point found for plugin {actual_name}")
                return
            
            spec = importlib.util.spec_from_file_location(
                f"plugins.{actual_name}", 
                module_file
            )
            if spec is None or spec.loader is None:
                self.logger.error(f"Failed to create module spec for plugin {actual_name}")
                return
            
            module = importlib.util.module_from_spec(spec)
            if str(plugin_dir) not in sys.path:
                sys.path.insert(0, str(plugin_dir))
            
            try:
                spec.loader.exec_module(module)
                
                plugin_instance = None
                if hasattr(module, 'create_plugin'):
                    plugin_instance = module.create_plugin()
                elif hasattr(module, 'plugin'):
                    plugin_instance = module.plugin
                else:
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, Plugin) and 
                            attr is not Plugin):
                            plugin_instance = attr()
                            break
                
                if plugin_instance is None:
                    self.logger.error(f"No Plugin instance found in {actual_name}")
                    return
                
                if not isinstance(plugin_instance, Plugin):
                    self.logger.error(f"Invalid plugin type in {actual_name}")
                    return
                
                setattr(plugin_instance, '_plugin_dir', plugin_dir)
                setattr(plugin_instance, '_actual_name', actual_name)
                setattr(plugin_instance, '_directory_name', plugin_name)
                setattr(plugin_instance, '_enabled', not is_disabled)
                
                self.plugins.append(plugin_instance)
                if not is_disabled:
                    for callback in plugin_instance.callbacks:
                        if callback.enabled:
                            self.callbacks[callback.position].append(callback)
                status = "disabled" if is_disabled else "enabled"
                self.logger.info(f"Successfully loaded plugin: {plugin_instance.metadata.name} ({status})")
                
            finally:
                if str(plugin_dir) in sys.path:
                    sys.path.remove(str(plugin_dir))
                    
        except Exception as e:
            self.logger.error(f"Failed to load plugin {actual_name}: {e}")
    
    def initialize_plugins(self, context: CallbackContext) -> None:
        """
        Initialize all enabled plugins.
        """
        self.logger.info("Initializing plugins")
        
        for plugin in self.plugins:
            if not self.is_plugin_enabled(plugin):
                continue
                
            try:
                if not plugin.initialize(context):
                    self.logger.warning(f"Plugin {plugin.metadata.name} initialization failed")
                else:
                    self.logger.debug(f"Plugin {plugin.metadata.name} initialized successfully")
            except Exception as e:
                self.logger.error(f"Error initializing plugin {plugin.metadata.name}: {e}")
    
    def shutdown_plugins(self, context: CallbackContext) -> None:
        """
        Shutdown all plugins.
        """
        self.logger.info("Shutting down plugins")
        
        for plugin in self.plugins:
            try:
                plugin.shutdown(context)
                self.logger.debug(f"Plugin {plugin.metadata.name} shut down successfully")
            except Exception as e:
                self.logger.error(f"Error shutting down plugin {plugin.metadata.name}: {e}")
    
    def trigger_callbacks(self, position: CallbackPosition, context: CallbackContext) -> None:
        """
        Trigger all callbacks for a specific position.
        
        Args:
            position: The callback position to trigger
            context: The context to pass to callbacks
        """
        callbacks = self.callbacks.get(position, [])
        
        if not callbacks:
            return
        
        self.logger.debug(f"Triggering {len(callbacks)} callbacks for position {position.value}")
        
        for callback in callbacks:
            if not callback.enabled:
                continue
                
            try:
                result = callback(context)
                if result is False:
                    self.logger.debug(f"Callback {callback.__class__.__name__} stopped further processing")
                    break
            except Exception as e:
                self.logger.error(f"Error in callback {callback.__class__.__name__}: {e}")
    
    def get_plugin(self, name: str) -> Plugin | None:
        """
        Get a plugin by name.
        """
        for plugin in self.plugins:
            if plugin.metadata.name == name:
                return plugin
        return None
    
    def is_plugin_enabled(self, plugin: Plugin) -> bool:
        """
        Check if a plugin is enabled based on its directory name.
        """
        directory_name = getattr(plugin, '_directory_name', '')
        return not directory_name.endswith('.disabled')
    
    def set_plugin_enabled(self, name: str, enabled: bool, context: CallbackContext | None = None) -> bool:
        """
        Enable or disable a plugin by renaming its directory.
        """
        plugin = self.get_plugin(name)
        if not plugin:
            self.logger.error(f"Plugin {name} not found")
            return False
        
        actual_name = getattr(plugin, '_actual_name', name)
        current_dir_name = getattr(plugin, '_directory_name', name)
        
        plugin_dir = None
        for d in self.plugins_dir.iterdir():
            if d.is_dir() and d.name == current_dir_name:
                plugin_dir = d
                break
        
        if not plugin_dir:
            self.logger.error(f"Could not find directory for plugin {name}")
            return False
        
        if enabled:
            new_dir_name = actual_name
        else:
            new_dir_name = f"{actual_name}.disabled"
        
        if current_dir_name == new_dir_name:
            return True
        
        new_path = plugin_dir.parent / new_dir_name
        try:
            plugin_dir.rename(new_path)
            self.logger.info(f"{'Enabled' if enabled else 'Disabled'} plugin {name}")
            
            setattr(plugin, '_directory_name', new_dir_name)
            setattr(plugin, '_enabled', enabled)
            self._update_plugin_callbacks(plugin, enabled, context)
            return True
            
        except Exception as e:
            self.logger.error(f"Error renaming plugin directory for {name}: {e}")
            return False
    
    def _update_plugin_callbacks(self, plugin: Plugin, enabled: bool, context: CallbackContext | None = None):
        """
        Update callback registrations for a plugin.
        """
        for position in CallbackPosition:
            self.callbacks[position] = [
                cb for cb in self.callbacks[position] 
                if cb not in plugin.callbacks
            ]
        
        if enabled:
            for callback in plugin.callbacks:
                if callback.enabled:
                    self.callbacks[callback.position].append(callback)
            
            for position in CallbackPosition:
                self.callbacks[position].sort(key=lambda cb: cb.priority)
            
            if context:
                try:
                    if plugin.initialize(context):
                        launch_callbacks = [cb for cb in plugin.callbacks if cb.position == CallbackPosition.ON_LAUNCH]
                        for callback in launch_callbacks:
                            if callback.enabled:
                                try:
                                    callback(context)
                                except Exception as e:
                                    self.logger.error(f"Error in launch callback for {plugin.metadata.name}: {e}")
                    else:
                        self.logger.warning(f"Plugin {plugin.metadata.name} initialization failed")
                except Exception as e:
                    self.logger.error(f"Error initializing plugin {plugin.metadata.name}: {e}")
        else:
            if context:
                try:
                    exit_callbacks = [cb for cb in plugin.callbacks if cb.position == CallbackPosition.ON_EXIT]
                    for callback in exit_callbacks:
                        if callback.enabled:
                            try:
                                callback(context)
                            except Exception as e:
                                self.logger.error(f"Error in exit callback for {plugin.metadata.name}: {e}")
                    
                    plugin.shutdown(context)
                except Exception as e:
                    self.logger.error(f"Error shutting down plugin {plugin.metadata.name}: {e}")
    
    def get_plugin_by_name(self, name: str) -> Plugin | None:
        """
        Get a plugin by its metadata name.
        """
        for plugin in self.plugins:
            if plugin.metadata.name == name:
                return plugin
        return None
    
    def get_all_plugins_info(self) -> list[dict[str, Any]]:
        """
        Get information about all plugins.
        """
        plugins_info = []
        for plugin in self.plugins:
            actual_name = getattr(plugin, '_actual_name', plugin.metadata.name)
            directory_name = getattr(plugin, '_directory_name', plugin.metadata.name)
            is_enabled = self.is_plugin_enabled(plugin)
            
            plugins_info.append({
                'name': plugin.metadata.name,
                'actual_name': actual_name,
                'version': plugin.metadata.version,
                'description': plugin.metadata.description,
                'author': plugin.metadata.author,
                'enabled': is_enabled,
                'directory_name': directory_name,
                'plugin_instance': plugin
            })
        
        return plugins_info
    
    def check_for_plugin_changes(self) -> dict[str, Any]:
        """
        Check for changes in the plugins directory.
        Returns dict with 'new', 'deleted', 'renamed' keys containing lists of plugin names.
        """
        if not self.plugins_dir.exists():
            return {'new': [], 'deleted': [], 'renamed': []}
        current_dirs = {d.name for d in self.plugins_dir.iterdir() 
                       if d.is_dir() and not d.name.startswith('__')}
        loaded_dirs = {getattr(plugin, '_directory_name', plugin.metadata.name) 
                      for plugin in self.plugins}
        def get_base_name(name):
            return name[:-9] if name.endswith('.disabled') else name
        current_base_names = {get_base_name(d): d for d in current_dirs}
        loaded_base_names = {get_base_name(d): d for d in loaded_dirs}
        new_base_names = set(current_base_names.keys()) - set(loaded_base_names.keys())
        new_plugins = [current_base_names[base] for base in new_base_names]
        deleted_base_names = set(loaded_base_names.keys()) - set(current_base_names.keys())
        deleted_plugins = [loaded_base_names[base] for base in deleted_base_names]
        renamed_plugins = []
        common_base_names = set(current_base_names.keys()) & set(loaded_base_names.keys())
        for base_name in common_base_names:
            current_dir = current_base_names[base_name]
            loaded_dir = loaded_base_names[base_name]
            if current_dir != loaded_dir:
                renamed_plugins.append((loaded_dir, current_dir))
        
        return {
            'new': new_plugins,
            'deleted': deleted_plugins,
            'renamed': renamed_plugins
        }
    
    def handle_renamed_plugins(self, renamed_plugins: list[tuple[str, str]], context: CallbackContext | None = None) -> list[str]:
        """
        Handle renamed plugins (enabled/disabled state changes).
        Returns list of plugin names that were renamed.
        """
        renamed_names = []
        
        for old_dir_name, new_dir_name in renamed_plugins:
            plugin = None
            for p in self.plugins:
                if getattr(p, '_directory_name', p.metadata.name) == old_dir_name:
                    plugin = p
                    break
            
            if plugin:
                renamed_names.append(plugin.metadata.name)
                setattr(plugin, '_directory_name', new_dir_name)
                is_enabled = not new_dir_name.endswith('.disabled')
                setattr(plugin, '_enabled', is_enabled)
                self._update_plugin_callbacks(plugin, is_enabled, context)
                status_change = "enabled" if is_enabled else "disabled"
                self.logger.info(f"Plugin {plugin.metadata.name} was {status_change} (renamed from {old_dir_name} to {new_dir_name})")
        
        return renamed_names
    
    def handle_deleted_plugins(self, deleted_plugins: list[str], context: CallbackContext | None = None) -> list[str]:
        """
        Handle deleted plugins by triggering their exit callbacks and removing them.
        Returns list of plugin names that were deleted.
        """
        deleted_names = []
        
        for plugin in self.plugins[:]:
            directory_name = getattr(plugin, '_directory_name', plugin.metadata.name)
            if directory_name in deleted_plugins:
                deleted_names.append(plugin.metadata.name)
                if context:
                    try:
                        exit_callbacks = [cb for cb in plugin.callbacks if cb.position == CallbackPosition.ON_EXIT]
                        for callback in exit_callbacks:
                            if callback.enabled:
                                try:
                                    callback(context)
                                except Exception as e:
                                    self.logger.error(f"Error in exit callback for {plugin.metadata.name}: {e}")
                        
                        plugin.shutdown(context)
                    except Exception as e:
                        self.logger.error(f"Error shutting down deleted plugin {plugin.metadata.name}: {e}")
                
                for position in CallbackPosition:
                    self.callbacks[position] = [
                        cb for cb in self.callbacks[position] 
                        if cb not in plugin.callbacks
                    ]
                
                self.plugins.remove(plugin)
                self.logger.info(f"Removed deleted plugin: {plugin.metadata.name}")
        
        return deleted_names


plugin_manager: PluginManager | None = None


def get_plugin_manager() -> PluginManager | None:
    """Get the global plugin manager instance."""
    return plugin_manager


def init_plugin_manager(plugins_dir: str, logger: Any) -> PluginManager:
    """Initialize the global plugin manager."""
    global plugin_manager
    plugin_manager = PluginManager(plugins_dir, logger)
    return plugin_manager
