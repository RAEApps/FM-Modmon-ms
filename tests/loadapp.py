"""The monitor (fm-modmon-ms.py, one folder up) loaded as a module for the tests."""
import importlib.util
import os


def load_app(path=None):
    """fm-modmon-ms.py as a module (or the copy at `path`)."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fm-modmon-ms.py')
    spec = importlib.util.spec_from_file_location('fm_modmon', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
