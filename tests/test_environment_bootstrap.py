import os
import subprocess
import sys
from pathlib import Path


def test_environment_is_loaded_before_authentication_settings_are_cached(tmp_path):
    script = '''
import os
import sys
import dotenv

calls = []
def load_dotenv(*args, **kwargs):
    calls.append(True)
    os.environ['VALID_API_KEYS'] = 'synthetic-bootstrap-key'
    return True
dotenv.load_dotenv = load_dotenv
import main
from middleware.auth import _VALID_KEYS
assert calls == [True]
assert _VALID_KEYS == frozenset({'synthetic-bootstrap-key'})
assert main.app is not None
'''
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, 'VALID_API_KEYS': '', 'DATA_DIR': str(tmp_path),
           'APP_ENV': 'test', 'DATABASE_URL': '', 'PYTHON_DOTENV_DISABLED': '1'}
    result = subprocess.run([sys.executable, '-c', script], cwd=root, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
