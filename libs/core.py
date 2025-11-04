import json
from os import path

class FkUSTChat_Core:
    def __init__(self):
        self.adapters = {}
        self.models = {}

        self.CONFIG_FILE = path.join(path.dirname(__file__), "../config")
        self.config = {}
        self.load_config()
    
    def add_model(self, model_name, model):
        """
        Adds a model to the core system.
        
        :param model_name: The name of the model.
        :param model: The model instance to be added.
        """
        if model_name in self.models:
            raise ValueError(f"Model {model_name} already exists.")
        self.models[model_name] = model
    
    def register_adapter(self, adapter):
        """
        Registers an adapter with the core system.
        
        :param adapter: The adapter instance to be registered.
        """
        if adapter.name in self.adapters:
            raise ValueError(f"Adapter {adapter.name} already exists.")
        self.adapters[adapter.name] = adapter
        if adapter.name in self.config:
            adapter.load_config(self.config[adapter.name])
        for model_name, model in adapter.models.items():
            self.add_model(f'__{adapter.name}__{model_name}', model)
        return adapter.name
    
    def set_adapter_config(self, adapter_name, key, config):
        """
        Sets the config for a specific adapter.
        
        :param adapter_name: The name of the adapter.
        :param config: The config data to be set for the adapter.
        """
        if adapter_name not in self.config:
            self.config[adapter_name] = {}

        self.config[adapter_name][key] = config
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)
    
    def load_config(self):
        """
        Loads the config from the config file.
        """
        if path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {}