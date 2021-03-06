#!/usr/bin/env python3
# This script generates dut.v file for testing TinyFPGA Bootloader

# Disable pylint's E1101, which breaks completely on migen
# pylint:disable=E1101

from migen import Module, Signal, Instance, ClockDomain, If
from migen.fhdl.specials import TSTriple
from migen.fhdl.structure import ResetSignal

from litex.build.generic_platform import Pins, Subsignal
from litex.build.sim.platform import SimPlatform
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import SoCCore

import argparse

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
        Subsignal("clk16", Pins(1)),
     ),
    ("reset", 0, Pins(1)),
]

_connectors = []


class Platform(SimPlatform):
    def __init__(self, toolchain="verilator"):
        SimPlatform.__init__(self, "sim", _io, _connectors,
                             toolchain="verilator")

    def create_programmer(self):
        raise ValueError("programming is not supported")


class _CRG(Module):
    def __init__(self, platform):
        clk = platform.request("clk")
        rst = platform.request("reset")

        clk12 = Signal()

        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_usb_12 = ClockDomain()
        self.clock_domains.cd_usb_16 = ClockDomain()
        self.clock_domains.cd_usb_48 = ClockDomain()
        self.clock_domains.cd_usb_48_to_12 = ClockDomain()

        clk48 = clk.clk48
        clk16 = clk.clk16
        self.comb += clk.clk12.eq(clk12)

        self.comb += self.cd_usb_16.clk.eq(clk16)
        self.comb += self.cd_usb_48.clk.eq(clk48)
        self.comb += self.cd_usb_48_to_12.clk.eq(clk48)

        clk12_counter = Signal(2)
        self.sync.usb_48_to_12 += clk12_counter.eq(clk12_counter + 1)

        self.comb += clk12.eq(clk12_counter[1])

        self.comb += self.cd_sys.clk.eq(clk12)
        self.comb += self.cd_usb_12.clk.eq(clk12)

        self.comb += [
            ResetSignal("sys").eq(rst),
            ResetSignal("usb_12").eq(rst),
            ResetSignal("usb_48").eq(rst),
        ]


class BaseSoC(SoCCore):
    SoCCore.csr_map = {
        "ctrl":           0,  # provided by default (optional)
        "crg":            1,  # user
        "cpu_or_bridge":  8,
        "usb":            9,
    }

    interrupt_map = {
        "usb": 3,
    }
    interrupt_map.update(SoCCore.interrupt_map)

    def __init__(self, platform, output_dir="build", **kwargs):
        # Disable integrated RAM as we'll add it later
        self.integrated_sram_size = 0

        self.output_dir = output_dir

        clk_freq = int(12e6)
        self.submodules.crg = _CRG(platform)

        SoCCore.__init__(self, platform, clk_freq,
                         cpu_type=None,
                         integrated_rom_size=0x0,
                         integrated_sram_size=0x0,
                         integrated_main_ram_size=0x0,
                         csr_address_width=14, csr_data_width=8,
                         with_uart=False, with_timer=False)

        # USB signals
        usb_p_tx = Signal()
        usb_n_tx = Signal()
        usb_p_rx = Signal()
        usb_n_rx = Signal()
        usb_tx_en = Signal()

        usb_p_t = TSTriple()
        usb_n_t = TSTriple()

        usb_pads = platform.request("usb")

        # Assign signals to triple
        self.comb += [
            If(usb_tx_en,
                usb_p_rx.eq(0b1),
                usb_n_rx.eq(0b0),
               ).Else(
                usb_p_rx.eq(usb_p_t.i),
                usb_n_rx.eq(usb_n_t.i),
            ),
            usb_p_t.oe.eq(usb_tx_en),
            usb_n_t.oe.eq(usb_tx_en),
            usb_p_t.o.eq(usb_p_tx),
            usb_n_t.o.eq(usb_n_tx),
        ]

        # Assign pads to triple
        self.specials += usb_p_t.get_tristate(usb_pads.d_p)
        self.specials += usb_n_t.get_tristate(usb_pads.d_n)
        self.comb += usb_pads.tx_en.eq(usb_tx_en)
        self.comb += usb_pads.pullup.eq(0b1)

        platform.add_source("../tinyfpga/common/tinyfpga_bootloader.v")
        self.specials += Instance("tinyfpga_bootloader",
                                  i_clk_48mhz=self.crg.cd_usb_48.clk,
                                  i_clk=self.crg.cd_usb_48.clk,
                                  i_reset=self.crg.cd_sys.rst,
                                  # USB lines
                                  o_usb_p_tx=usb_p_tx,
                                  o_usb_n_tx=usb_n_tx,
                                  i_usb_p_rx=usb_p_rx,
                                  i_usb_n_rx=usb_n_rx,
                                  o_usb_tx_en=usb_tx_en
                                  )


def main():
    parser = argparse.ArgumentParser(
        description="Build test file for dummy or eptri module")
    parser.add_argument('--dir', metavar='DIRECTORY',
                        default='build',
                        help='Output directory (default: %(default)s)')
    parser.add_argument('--csr', metavar='CSR',
                        default='csr.csv',
                        help='csr file (default: %(default)s)')
    args = parser.parse_args()
    output_dir = args.dir

    platform = Platform()
    soc = BaseSoC(platform,
                  cpu_type=None, cpu_variant=None,
                  output_dir=output_dir)
    builder = Builder(soc, output_dir=output_dir,
                      csr_csv=args.csr,
                      compile_software=False)
    vns = builder.build(run=False,
                        build_name="dut")
    soc.do_exit(vns)

    print("""Simulation build complete.  Output files:
    {}/gateware/dut.v               Source Verilog file. Run this under Cocotb.
""".format(output_dir))


if __name__ == "__main__":
    main()
