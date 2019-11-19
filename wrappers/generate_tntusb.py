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
from litex.soc.integration.soc_core import (soc_core_argdict, soc_core_args,
                                            get_mem_data, SoCCore)
from litex.soc.integration.builder import Builder, builder_args

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
    (
        "wishbone",
        0,
        Subsignal("adr", Pins(30)),
        Subsignal("dat_r", Pins(32)),
        Subsignal("dat_w", Pins(32)),
        Subsignal("sel", Pins(4)),
        Subsignal("cyc", Pins(1)),
        Subsignal("stb", Pins(1)),
        Subsignal("ack", Pins(1)),
        Subsignal("we", Pins(1)),
        Subsignal("cti", Pins(3)),
        Subsignal("bte", Pins(2)),
        Subsignal("err", Pins(1))
    ),

    (
        "serial", 0,
        Subsignal("tx", Pins("D10")),
        Subsignal("rx", Pins("A9"))
    ),
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

    SoCCore.mem_map = {
        "rom":  0x00010000,  # (default shadow @0x80000000)
        "sram": 0x00020000,  # (default shadow @0xa0000000)
        "main_ram": 0x00030000,  # (default shadow @0xc0000000)
        "csr": 0xe0000000,
    }

    interrupt_map = {
        "usb": 3,
    }
    interrupt_map.update(SoCCore.interrupt_map)

    def __init__(self,
                 platform,
                 output_dir="build",
                 **kwargs):
        kwargs['cpu_reset_address'] = 0x0

        self.output_dir = output_dir

        clk_freq = int(48e6)
        self.submodules.crg = _CRG(platform)

        SoCCore.__init__(self,
                         platform,
                         clk_freq,
                         integrated_rom_size= 0x000c000,
                         integrated_sram_size=0x0004000,
                         integrated_main_ram_size=0x03f0,
                         with_uart=True,
                         **kwargs)

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
        #for i in range(4):
        #    tx_en_tmp = Signal()
        #    self.sync.sys += tx_en_tmp.eq(usb_tx_en)
        #    usb_tx_en = tx_en_tmp

        self.comb += usb_reset.eq(~self.crg.cd_sys.rst)
        # Assign pads to triple
        self.specials += usb_p_t.get_tristate(usb_pads.d_p)
        self.specials += usb_n_t.get_tristate(usb_pads.d_n)
        # Deasserting tx_en should not be delayed
        self.comb += usb_pads.tx_en.eq(usb_tx_en & ~usb_tx_en_dut)

        class _WishboneBridge(Module):
            def __init__(self, interface):
                self.wishbone = interface

        self.submodules.wb = _WishboneBridge(
                self.platform.request("wishbone"))
        self.add_wb_master(self.wb.wishbone)

        # USB Core
        #         EP Buffer
        ep_tx_addr_0 = Signal(9)
        ep_tx_data_0 = Signal(32)
        ep_tx_we_0 = Signal()

        ep_rx_addr_0 = Signal(9)
        ep_rx_data_1 = Signal(32)
        ep_rx_re_0 = Signal()

        ep_tx_addr_0 = self.wb.wishbone.adr
        ep_tx_data_0 = self.wb.wishbone.dat_w
        ep_tx_we_0 = self.wb.wishbone.we & ~self.wb.wishbone.ack & self.wb.wishbone.cyc  # ???

        ep_rx_addr_0 = self.wb.wishbone.adr
        ep_rx_data_1 = self.wb.wishbone.dat_r  # ???
        ep_rx_re_0 = 1

        #     Bus interface
        ub_addr = Signal(12)
        ub_wdata = Signal(16)
        ub_rdata = Signal(16)
        ub_cyc = Signal()
        ub_we = Signal()
        ub_ack = Signal()

        ub_addr = self.wb.wishbone.adr
        ub_wdata = self.wb.wishbone.dat_w
        ub_rdata = self.wb.wishbone.dat_r
        ub_cyc = self.wb.wishbone.cyc
        ub_we = self.wb.wishbone.we
        ub_ack = self.wb.wishbone.ack

        #     Core
        platform.add_source("../ice40-playground/cores/usb/rtl/usb.v")
        self.specials += Instance("usb",
                                  p_EPDW=32,
                                  # Pads
                                  io_pad_dp=usb_pads.d_p,
                                  io_pad_dn=usb_pads.d_n,
                                  o_pad_pu=usb_pads.pullup,
                                  # EP buffer interface
                                  i_ep_tx_addr_0=ep_tx_addr_0,
                                  i_ep_tx_data_0=ep_tx_data_0,
                                  i_ep_tx_we_0=ep_tx_we_0,
                                  i_ep_rx_addr_0=ep_rx_addr_0,
                                  o_ep_rx_data_1=ep_rx_data_1,
                                  i_ep_rx_re_0=ep_rx_re_0,
                                  i_ep_clk=self.crg.cd_sys.clk,
                                  # Bus interface
                                  i_bus_addr=ub_addr,
                                  i_bus_din=ub_wdata,
                                  o_bus_dout=ub_rdata,
                                  i_bus_cyc=ub_cyc,
                                  i_bus_we=ub_we,
                                  o_bus_ack=ub_ack,
                                  # IRQ
                                  # output wire irq,
                                  # SOF indication
                                  # output wire sof,
                                  # Common
                                  i_clk=self.crg.cd_sys.clk,
                                  i_rst=self.crg.cd_sys.rst
                                  )


def main():
    parser = argparse.ArgumentParser(
        description="Build test file for dummy or eptri module")
    builder_args(parser)
    soc_core_args(parser)
    parser.add_argument('--dir',
                        metavar='DIRECTORY',
                        default='build',
                        help='Output directory (defauilt: %(default)s)')
    parser.add_argument('--csr',
                        metavar='CSR',
                        default='csr.csv',
                        help='csr file (default: %(default)s)')
    parser.add_argument("--rom-init", default=None, help="rom_init file")
    args = parser.parse_args()

    soc_kwargs = soc_core_argdict(args)
    if args.rom_init is not None:
        soc_kwargs["integrated_rom_init"] = \
            get_mem_data(args.rom_init, endianness='little')
    output_dir = args.dir

    platform = Platform()
    soc = BaseSoC(platform, **soc_kwargs)
    builder = Builder(soc,
                      output_dir=output_dir,
                      csr_csv=args.csr,
                      compile_software=False)
    vns = builder.build(run=False)
    soc.do_exit(vns)

    print("""Simulation build complete.  Output files:
    {}/gateware/dut.v               Source Verilog file. Run this under Cocotb.
""".format(output_dir))


if __name__ == "__main__":
    main()
