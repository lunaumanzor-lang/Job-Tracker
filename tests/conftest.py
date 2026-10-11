import sys
import os

# Asegurar que el directorio raíz del proyecto esté en el sys.path para pytest
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
