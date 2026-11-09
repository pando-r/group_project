import atexit
import os
import shutil
import tempfile
from pathlib import Path

# Keep every test offline, regardless of the developer shell's tracing config.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["LLM_MOCK"] = "1"

# Never point tests at the developer's demo database or checkpoint file.
_TEST_DIR = Path(tempfile.mkdtemp(prefix="medrisk-tests-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TEST_DIR / 'test.db').as_posix()}"
os.environ["AGENT_CHECKPOINT_PATH"] = (_TEST_DIR / "checkpoints.db").as_posix()
os.environ["AUTO_CREATE_TABLES"] = "1"
os.environ["AUTO_SEED"] = "1"

atexit.register(shutil.rmtree, _TEST_DIR, ignore_errors=True)
