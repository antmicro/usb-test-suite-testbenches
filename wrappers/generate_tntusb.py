#!/usr/bin/env python3
# This script generates dut.v file for testing asics-ws usb1_device

# Disable pylint's E1101, which breaks completely on migen
# pylint:disable=E1101

import argparse

from migen import Module, Signal, Instance, ClockDomain, If
from migen.fhdl.specials import TSTriple
from migen.fhdl.structure import ResetSignal

from litex.build.generic_platform import Pins, Subsignal
from litex.build.sim.platform import SimPlatform
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.builder import Builder

_io = [
    (
        "usb",
        0,
        Subsignal("d_p", Pins(1)),
        Subsignal("d_n", Pins(1)),
        Subsignal("pullup", Pins(1)),
        Subsignal("tx_en", Pins(1)),
    ),
    # Wishbone
    ("wishbone", 0, Subsignal("adr", Pins(30)), Subsignal("dat_r", Pins(32)),
     Subsignal("dat_w",
               Pins(32)), Subsignal("sel", Pins(4)), Subsignal("cyc", Pins(1)),
     Subsignal("stb", Pins(1)), Subsignal("ack",
                                          Pins(1)), Subsignal("we", Pins(1)),
     Subsignal("cti", Pins(3)), Subsignal("bte",
                                          Pins(2)), Subsignal("err", Pins(1))),
    (
        "clk",
        0,
        Subsignal("clk48", Pins(1)),
    ),
    ("reset", 0, Pins(1)),
]

_connectors = []


class Platform(SimPlatform):
    def __init__(self, toolchain="verilator"):
        SimPlatform.__init__(self,
                             "sim",
                             _io,
                             _connectors,
                             toolchain="verilator")

    def create_programmer(self):
        raise ValueError("programming is not supported")


class _CRG(Module):
    def __init__(self, platform):
        clk = platform.request("clk")
        rst = platform.request("reset")

        self.clock_domains.cd_sys = ClockDomain()
        self.comb += self.cd_sys.clk.eq(clk.clk48)

        self.comb += [
            ResetSignal("sys").eq(rst),
        ]


class BaseSoC(SoCCore):
    SoCCore.csr_map = {
        "ctrl": 0,  # provided by default (optional)
        "crg": 1,  # user
        "cpu_or_bridge": 8,
        "usb": 9,
    }

    interrupt_map = {
        "usb": 3,
    }
    interrupt_map.update(SoCCore.interrupt_map)

    def __init__(self,
                 platform,
                 output_dir="build",
                 usb_variant='dummy',
                 **kwargs):
        # Disable integrated RAM as we'll add it later
        self.integrated_sram_size = 0

        self.output_dir = output_dir

        clk_freq = int(48e6)
        self.submodules.crg = _CRG(platform)

        SoCCore.__init__(self,
                         platform,
                         clk_freq,
                         cpu_type=None,
                         integrated_rom_size=0x0,
                         integrated_sram_size=0x0,
                         integrated_main_ram_size=0x0,
                         csr_address_width=14,
                         csr_data_width=8,
                         with_uart=False,
                         with_timer=False)

        # USB signals
        usb_p_tx = Signal()
        usb_n_tx = Signal()
        usb_p_rx = Signal()
        usb_n_rx = Signal()
        usb_tx_en = Signal()
        usb_tx_en_dut = Signal()
        usb_reset = Signal()

        usb_p_t = TSTriple()
        usb_n_t = TSTriple()

        usb_pads = platform.request("usb")

        # Assign signals to triple
        self.comb += [
            If(
                ~usb_tx_en_dut,
                usb_p_rx.eq(0b1),
                usb_n_rx.eq(0b0),
            ).Else(
                usb_p_rx.eq(usb_p_t.i),
                usb_n_rx.eq(usb_n_t.i),
            ),
            usb_p_t.oe.eq(~usb_tx_en_dut),
            usb_n_t.oe.eq(~usb_tx_en_dut),
            usb_p_t.o.eq(usb_p_tx),
            usb_n_t.o.eq(usb_n_tx),
        ]

        self.comb += usb_tx_en.eq(~usb_tx_en_dut)
        # Delay USB_TX_EN line
        for i in range(4):
            tx_en_tmp = Signal()
            self.sync.sys += tx_en_tmp.eq(usb_tx_en)
            usb_tx_en = tx_en_tmp

        self.comb += usb_reset.eq(~self.crg.cd_sys.rst)
        # Assign pads to triple
        self.specials += usb_p_t.get_tristate(usb_pads.d_p)
        self.specials += usb_n_t.get_tristate(usb_pads.d_n)
        # Deasserting tx_en should not be delayed
        self.comb += usb_pads.tx_en.eq(usb_tx_en & ~usb_tx_en_dut)

        # SPI flash model supplied by tnt for simulation
        platform.add_source("../ice40-playground/projects/riscv_usb/sim/spiflash.v")
        spi_cs = Signal()
        spi_clk = Signal()
        spi_mosi = Signal()
        spi_miso = Signal()
        self.specials += Instance(
            "spiflash",
            i_csb=spi_cs,
            i_clk=spi_clk,
            io_io0=spi_mosi,
            io_io1=spi_miso,
            )

        platform.add_source("../ice40-playground/projects/riscv_usb/rtl/top.v")
        self.specials += Instance(
            "top",
            i_clk_in=self.crg.cd_sys.clk,
            i_ext_rst=~usb_reset,
            # SPI
            io_spi_mosi=spi_mosi,
            io_spi_miso=spi_miso,
            io_spi_flash_cs_n=spi_cs,
            io_spi_clk=spi_clk,
            # USB lines
            io_usb_dp=usb_pads.d_p,
            io_usb_dn=usb_pads.d_n,
            o_usb_pu=usb_pads.pullup,
            )


def generate(output_dir, csr_csv):
    platform = Platform()
    soc = BaseSoC(platform,
                  cpu_type=None,
                  cpu_variant=None,
                  output_dir=output_dir)
    builder = Builder(soc,
                      output_dir=output_dir,
                      csr_csv=csr_csv,
                      compile_software=False)
    vns = builder.build(run=False)
    soc.do_exit(vns)


def main():
    parser = argparse.ArgumentParser(
        description="Build test file for dummy or eptri module")
    parser.add_argument('--dir',
                        metavar='DIRECTORY',
                        default='build',
                        help='Output directory (defauilt: %(default)s)')
    parser.add_argument('--csr',
                        metavar='CSR',
                        default='csr.csv',
                        help='csr file (default: %(default)s)')
    args = parser.parse_args()
    output_dir = args.dir
    generate(output_dir, args.csr)

    print("""Simulation build complete.  Output files:
    {}/gateware/dut.v               Source Verilog file. Run this under Cocotb.
""".format(output_dir))


if __name__ == "__main__":
    main()
