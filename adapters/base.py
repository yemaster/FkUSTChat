class FkUSTChat_BaseAdapter:
    def __init__(self, context, adapter_info):
        """
        Initializes the base adapter with the given context and adapter information.
        
        :param context: The context in which the adapter operates.
        :param adapter_info: Information about the adapter, such as its name and configuration.
        """
        self.context = context
        self.adapter_info = adapter_info
        self.name = adapter_info.get('name', 'FkUSTChat_BaseAdapter')
        self.description = adapter_info.get('description', 'Base Adapter for FkUSTChat')
        self.author = adapter_info.get('author', 'yemaster')
        self.models = {}
        self.config = {}
    
    def load_config(self, config):
        """
        Loads the config into the adapter.
        
        :param config: The config data to be loaded.
        """
        self.config = config
    
    def set_config(self, key, config):
        """
        Sets the config for the adapter.
        
        :param key: The key under which to store the config data.
        :param config: The config data to be stored.
        """
        self.config[key] = config
        self.context.set_adapter_config(self.name, key, config)
        
class FkUSTChat_BaseModel:
    def __init__(self, adapter, model_info):
        """
        Initializes the base model with the given model information.
        
        :param model_info: Information about the model, such as its name and configuration.
        """
        self.adapter = adapter
        self.context = adapter.context
        self.model_info = model_info
        self.name = model_info.get('name', 'FkUSTChat_BaseModel')
        self.description = model_info.get('description', 'Base Model for FkUSTChat')
        self.author = model_info.get('author', 'yemaster')
        self.allow_tool = False
    
    def get_response(self, prompt):
        """
        Generates a response based on the given prompt.
        
        :param prompt: The input prompt for which to generate a response.
        :return: The generated response.
        """
        raise NotImplementedError("This method should be overridden by subclasses.")