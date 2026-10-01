import sys
from pathlib import Path
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path = [str(SCRIPTS)] + [x for x in sys.path if Path(x).resolve() != SCRIPTS.resolve()]
sys.modules.pop("ops_db", None)
