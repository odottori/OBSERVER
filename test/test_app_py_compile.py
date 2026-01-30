import os
import py_compile


def test_app_py_compiles():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app_path = os.path.join(root, 'app.py')
    py_compile.compile(app_path, doraise=True)
