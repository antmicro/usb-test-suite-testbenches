#!/usr/bin/env python3
# This script generates dut.v file for testing asics-ws usb1_device

# Disable pylint's E1101, which breaks completely on migen
# pylint:disable=E1101

import argparse

from migen import Module, Signal, Instance, ClockDomain, If
from migen.fhdl.structure import ResetSignal

from litex.build.generic_platform import Pins, Subsignal
from litex.build.sim.platform import SimPlatform
from litex.soc.integration.soc_core import (soc_core_argdict, soc_core_args,
                                            get_mem_data, SoCCore)
from litex.soc.integration.builder import Builder, builder_args
from litex.soc.interconnect import wishbone

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
        Subsignal("adr", Pins(32)),
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
        "main_ram": 0x00000000,  # (default shadow @0xc0000000)
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
                         integrated_rom_size=0x000c000,
                         integrated_sram_size=0x0004000,
                         integrated_main_ram_size=0x0400,
                         with_uart=True,
                         **kwargs)

        # Modify stack address for FW
        self.cpu.cpu_params.update(p_STACKADDR=0x00000400)

        usb_pads = platform.request("usb")

        # USB IP core bus interface (wb[4] in riscv project)
        self.wb_ub = wishbone.Interface()
        self.add_wb_slave(0x84000000, self.wb_ub, 1 << 16)

        # USB IP core Endpoint interface (wb[5] in riscv project)
        self.wb_ep = wishbone.Interface()
        self.add_wb_slave(0x85000000, self.wb_ep, 1 << 16)

        # USB Core
        #         EP Buffer
        ep_tx_addr_0 = Signal(9)
        ep_tx_data_0 = Signal(32)
        ep_tx_we_0 = Signal()

        ep_rx_addr_0 = Signal(9)
        ep_rx_data_1 = Signal(32)
        ep_rx_re_0 = Signal()

        ep_tx_addr_0 = self.wb_ep.adr
        ep_tx_data_0 = self.wb_ep.dat_w
        ep_tx_we_0 = self.wb_ep.we & ~self.wb_ep.ack & self.wb_ep.cyc

        ep_rx_addr_0 = self.wb_ep.adr
        self.comb += If(
                self.wb_ep.cyc == 1,
                # then
                self.wb_ep.dat_r.eq(ep_rx_data_1)
                ).Else(
                self.wb_ep.eq(0)
                )
        ep_rx_re_0 = 1

        # Automatic ACK with 1 cycle delay
        ack_tmp = Signal()
        self.sync.sys += ack_tmp.eq(self.wb_ep.cyc & ~self.wb_ep.ack)
        self.wb_ep.ack = ack_tmp

        #     Bus interface
        ub_addr = Signal(12)
        ub_wdata = Signal(16)
        ub_rdata = Signal(16)
        ub_cyc = Signal()
        ub_we = Signal()
        ub_ack = Signal()

        ub_addr = self.wb_ub.adr
        ub_wdata = self.wb_ub.dat_w
        ub_rdata = self.wb_ub.dat_r
        ub_cyc = self.wb_ub.cyc
        ub_we = self.wb_ub.we
        ub_ack = self.wb_ub.ack

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
