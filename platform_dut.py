from litex.build.generic_platform import Pins, IOStandard, Misc, Subsignal
from litex.build.sim.platform import SimPlatform

_io = [
    # Wishbone
    ("wishbone", 0,
        Subsignal("adr",   Pins(30)),
        Subsignal("dat_r", Pins(32)),
        Subsignal("dat_w", Pins(32)),
        Subsignal("sel",   Pins(4)),
        Subsignal("cyc",   Pins(1)),
        Subsignal("stb",   Pins(1)),
        Subsignal("ack",   Pins(1)),
        Subsignal("we",    Pins(1)),
        Subsignal("cti",   Pins(3)),
        Subsignal("bte",   Pins(2)),
        Subsignal("err",   Pins(1))
    ),
    ("usb", 0,
        Subsignal("d_p", Pins(1)),
        Subsignal("d_n", Pins(1)),
        Subsignal("pullup", Pins(1)),
        Subsignal("tx_en", Pins(1)),
    ),
    ("clk", 0,
        Subsignal("clk48", Pins(1)),
        Subsignal("clk12", Pins(1)),
    ),
    ("reset", 0, Pins(1)),
]

_connectors = []

class Platform(SimPlatform):
    def __init__(self, toolchain="verilator"):
        SimPlatform.__init__(self, "sim", _io, _connectors, toolchain="verilator")

    def create_programmer(self):
        raise ValueError("programming is not supported")
