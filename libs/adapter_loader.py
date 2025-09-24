from os import path, listdir
import importlib.util

from adapters.base import FkUSTChat_BaseAdapter

ADAPTER_DIR = path.join(path.dirname(__file__), "../adapters")

def get_adapter_files():
    """
    Returns a list of adapter files in the ADAPTER_DIR directory.
    """
    return [f for f in listdir(ADAPTER_DIR) if f.endswith('.py') and f != '__init__.py']

def load_adapter(context, adapter_filename):
    """
    Dynamically loads an adapter module given its filename.
    
    :param adapter_filename: The name of the adapter file (without .py extension).
    :return: The loaded adapter module.
    """
    if not adapter_filename.endswith('.py'):
        adapter_filename += '.py'
    
    # 从指定文件导入
    adapter_path = path.join(ADAPTER_DIR, adapter_filename)
    if not path.exists(adapter_path):
        raise FileNotFoundError(f"Adapter file {adapter_filename} does not exist in {ADAPTER_DIR}.")
    spec = importlib.util.spec_from_file_location(adapter_filename[:-3], adapter_path)
    adapter_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter_module)
    
    # 获取其中全部的 class
    adapter_classes = [getattr(adapter_module, attr) for attr in dir(adapter_module) if isinstance(getattr(adapter_module, attr), type)]
    # 这个 class 必须为 FkUSTChat_BaseAdapter 的子类，但是不包括 FkUSTChat_BaseAdapter 自身
    adapter_classes = [cls(context) for cls in adapter_classes if issubclass(cls, FkUSTChat_BaseAdapter) and cls is not FkUSTChat_BaseAdapter]
    
    successful_adapters = []
    for adapter in adapter_classes:
        try:
            successful_adapters.append(context.register_adapter(adapter))
        except Exception as e:
            print(f"Failed to register adapter {adapter.name}: {e}")
    
    return successful_adapters