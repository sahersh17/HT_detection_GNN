"""Apply the unchanged v1 held-out-host controls to typed port graphs."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "port_aware_v1/probe.py"
spec = importlib.util.spec_from_file_location("frozen_port_aware_v1_probe", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.OUT = HERE.parents[1] / "runs/port_aware_v2"

if __name__ == "__main__":
    module.main()
