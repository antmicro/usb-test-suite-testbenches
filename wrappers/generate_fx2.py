import os
import sys
import argparse

from migen import *

from litex.soc.interconnect import wishbone

from litex.build.generic_platform import Pins, Subsignal
from litex.build.sim.platform import SimPlatform
from litex.build.sim.config import SimConfig

from fx2.soc import FX2, FX2CRG


_io = [
    ("reset", 0, Pins(1)),
    ("clk", 0, Pins(1)),
    (
        'wishbone', 0,
        Subsignal('adr',   Pins(30)),
        Subsignal('dat_r', Pins(32)),
        Subsignal('dat_w', Pins(32)),
        Subsignal('sel',   Pins(4)),
        Subsignal('cyc',   Pins(1)),
        Subsignal('stb',   Pins(1)),
        Subsignal('ack',   Pins(1)),
        Subsignal('we',    Pins(1)),
        Subsignal('cti',   Pins(3)),
        Subsignal('bte',   Pins(2)),
        Subsignal('err',   Pins(1))
    ),
]


class SoC(FX2):
    def __init__(self, *args, **kwargs):
        # expose wishbone master for simulation purpose
        sim_wishbone = wishbone.Interface()
        kwargs['wb_masters'] = kwargs.get('wb_masters', []) + [sim_wishbone]
        super().__init__(*args, **kwargs)

        # connect wishbone to io pins
        wb = self.platform.request('wishbone')
        # copy wishbone layout, as there is no direction in _io, so .connect() won't work
        wb.layout = sim_wishbone.layout
        self.comb += wb.connect(sim_wishbone)

        # add clocks
        clk = self.platform.request('clk')
        rst = self.platform.request('reset')
        self.submodules.crg = FX2CRG(self.csr_bank, clk=clk, rst=rst)


def generate(code):
    platform = SimPlatform("sim", _io, toolchain="verilator")
    soc = SoC(platform, clk_freq=48e6, code=code)
    config = SimConfig(default_clk='clk48')
    vns = platform.build(soc, sim_config=config, build=True, run=False, trace=True,
                         build_dir=os.path.join('build', 'gateware'))
    soc.do_exit(vns)


def main():
    parser = argparse.ArgumentParser(
        description="TODO")
    parser.add_argument('--code',
                        help='Path to binary file with FX2 program')
    args = parser.parse_args()

    code = None
    if args.code:
        with open(args.code, 'rb') as f:
            code = list(f.read())

    generate(code)

    print("""Simulation build complete.  Output files:
    build/gateware/dut.v               Source Verilog file. Run this under Cocotb.
""")


if __name__ == "__main__":
    main()
