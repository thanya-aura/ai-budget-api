# budget_plus/tests/conftest.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # โฟลเดอร์ที่มี 'budget_plus'
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
