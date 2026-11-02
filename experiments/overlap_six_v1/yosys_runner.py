"""Use the installed YoWASP binary with room for deeply nested Verilog case trees."""
import sys
import threading
from unittest.mock import patch

import wasmtime
from wasmtime import _bindings as api
from yowasp_yosys import run_yosys


class FrontendConfig(wasmtime.Config):
    def __init__(self):
        super().__init__()
        api.wasmtime_config_async_stack_size_set(self.ptr(), 32 << 20)
        api.wasmtime_config_max_wasm_stack_set(self.ptr(), 16 << 20)


if __name__=="__main__":
    threading.stack_size(64 << 20)
    with patch.object(wasmtime, "Config", FrontendConfig):
        sys.exit(run_yosys(sys.argv[1:]))
