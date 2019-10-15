#!/usr/bin/env python3

from migen import Module, Signal, ClockDomain, Instance, If
from migen.fhdl.specials import TSTriple
from migen.fhdl.structure import ClockSignal, ResetSignal, Replicate, Cat
from migen.fhdl.bitcontainer import bits_for

from litex.build.sim.platform import SimPlatform
from litex.build.generic_platform import Pins, IOStandard, Subsignal
from litex.soc.integration import SoCCore
from litex.soc.integration.builder import Builder, builder_args
from litex.soc.integration.soc_core import (soc_core_argdict, soc_core_args,
                                            get_mem_data)
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import AutoCSR, CSRStatus, CSRStorage


from valentyusb.usbcore import io as usbio
from valentyusb.usbcore.cpu import dummyusb, eptri, epfifo

import argparse
import os

_io = [
    # Wishbone
    ("wishbone", 0, Subsignal("adr", Pins(30)), Subsignal("dat_r", Pins(32)),
     Subsignal("dat_w",
               Pins(32)), Subsignal("sel", Pins(4)), Subsignal("cyc", Pins(1)),
     Subsignal("stb", Pins(1)), Subsignal("ack",
                                          Pins(1)), Subsignal("we", Pins(1)),
     Subsignal("cti", Pins(3)), Subsignal("bte",
                                          Pins(2)), Subsignal("err", Pins(1))),
    ("serial", 0, Subsignal("tx", Pins("J20")), Subsignal("rx", Pins("K21")),
     IOStandard("LVCMOS33")),
    (
        "usb",
        0,
        Subsignal("d_p", Pins(1)),
        Subsignal("d_n", Pins(1)),
        Subsignal("pullup", Pins(1)),
        Subsignal("tx_en", Pins(1)),
    ),
    ("spiflash", 0,
        Subsignal("cs_n", Pins("C1"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("D1"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("E1"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("F1"), IOStandard("LVCMOS33")),
        Subsignal("wp",   Pins("A1"), IOStandard("LVCMOS33")),
        Subsignal("hold", Pins("B1"), IOStandard("LVCMOS33")),
    ),
    (
        "clk",
        0,
        Subsignal("clk48", Pins(1)),
        Subsignal("clk12", Pins(1)),
    ),
    ("reset", 0, Pins(1)),
]

_connectors = []


class _CRG(Module):
    def __init__(self, platform):
        clk = platform.request("clk")
        rst = platform.request("reset")

        clk12 = Signal()

        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_usb_12 = ClockDomain()
        self.clock_domains.cd_usb_48 = ClockDomain()
        self.clock_domains.cd_usb_48_to_12 = ClockDomain()

        clk48 = clk.clk48
        self.comb += clk.clk12.eq(clk12)

        self.comb += self.cd_usb_48.clk.eq(clk48)
        self.comb += self.cd_usb_48_to_12.clk.eq(clk48)

        clk12_counter = Signal(2)
        self.sync.usb_48_to_12 += clk12_counter.eq(clk12_counter + 1)

        self.comb += clk12.eq(clk12_counter[1])

        self.comb += self.cd_sys.clk.eq(clk48)
        self.comb += self.cd_usb_12.clk.eq(clk12)

        self.comb += [
            ResetSignal("sys").eq(rst),
            ResetSignal("usb_12").eq(rst),
            ResetSignal("usb_48").eq(rst),
        ]

class PicoRVSpi(Module, AutoCSR):
    def __init__(self, platform, pads, size=2*1024*1024):
        self.size = size

        self.bus = bus = wishbone.Interface()

        self.reset = Signal()

        self.cfg1 = CSRStorage(size=8)
        self.cfg2 = CSRStorage(size=8)
        self.cfg3 = CSRStorage(size=8)
        self.cfg4 = CSRStorage(size=8)

        self.stat1 = CSRStatus(size=8)
        self.stat2 = CSRStatus(size=8)
        self.stat3 = CSRStatus(size=8)
        self.stat4 = CSRStatus(size=8)

        cfg = Signal(32)
        cfg_we = Signal(4)
        cfg_out = Signal(32)
        self.comb += [
            cfg.eq(Cat(self.cfg1.storage, self.cfg2.storage, self.cfg3.storage, self.cfg4.storage)),
            cfg_we.eq(Cat(self.cfg1.re, self.cfg2.re, self.cfg3.re, self.cfg4.re)),
            self.stat1.status.eq(cfg_out[0:8]),
            self.stat2.status.eq(cfg_out[8:16]),
            self.stat3.status.eq(cfg_out[16:24]),
            self.stat4.status.eq(cfg_out[24:32]),
        ]

        mosi_pad = TSTriple()
        miso_pad = TSTriple()
        cs_n_pad = TSTriple()
        clk_pad  = TSTriple()
        wp_pad   = TSTriple()
        hold_pad = TSTriple()
        self.specials += mosi_pad.get_tristate(pads.mosi)
        self.specials += miso_pad.get_tristate(pads.miso)
        self.specials += cs_n_pad.get_tristate(pads.cs_n)
        self.specials += clk_pad.get_tristate(pads.clk)
        self.specials += wp_pad.get_tristate(pads.wp)
        self.specials += hold_pad.get_tristate(pads.hold)

        reset = Signal()
        self.comb += [
            reset.eq(ResetSignal() | self.reset),
            cs_n_pad.oe.eq(~reset),
            clk_pad.oe.eq(~reset),
        ]

        flash_addr = Signal(24)
        # size/4 because data bus is 32 bits wide, -1 for base 0
        mem_bits = bits_for(int(size/4)-1)
        pad = Signal(2)
        self.comb += flash_addr.eq(Cat(pad, bus.adr[0:mem_bits-1]))

        read_active = Signal()
        spi_ready = Signal()
        self.sync += [
            If(bus.stb & bus.cyc & ~read_active,
                read_active.eq(1),
                bus.ack.eq(0),
            )
            .Elif(read_active & spi_ready,
                read_active.eq(0),
                bus.ack.eq(1),
            )
            .Else(
                bus.ack.eq(0),
                read_active.eq(0),
            )
        ]

        o_rdata = Signal(32)
        self.comb += bus.dat_r.eq(o_rdata)

        self.specials += Instance("spimemio",
            o_flash_io0_oe = mosi_pad.oe,
            o_flash_io1_oe = miso_pad.oe,
            o_flash_io2_oe = wp_pad.oe,
            o_flash_io3_oe = hold_pad.oe,

            o_flash_io0_do = mosi_pad.o,
            o_flash_io1_do = miso_pad.o,
            o_flash_io2_do = wp_pad.o,
            o_flash_io3_do = hold_pad.o,
            o_flash_csb    = cs_n_pad.o,
            o_flash_clk    = clk_pad.o,

            i_flash_io0_di = mosi_pad.i,
            i_flash_io1_di = miso_pad.i,
            i_flash_io2_di = wp_pad.i,
            i_flash_io3_di = hold_pad.i,

            i_resetn = ~reset,
            i_clk = ClockSignal(),

            i_valid = bus.stb & bus.cyc,
            o_ready = spi_ready,
            i_addr  = flash_addr,
            o_rdata = o_rdata,

            i_cfgreg_we = cfg_we,
            i_cfgreg_di = cfg,
            o_cfgreg_do = cfg_out,
        )
        platform.add_source("../foboot/rtl/spimemio.v")


class FirmwareROM(wishbone.SRAM):
    def __init__(self, size, filename):
        data = []
        with open(filename, 'rb') as inp:
            data = inp.read()
        wishbone.SRAM.__init__(self, size, read_only=True, init=data)


class Platform(SimPlatform):
    def __init__(self, toolchain="verilator"):
        SimPlatform.__init__(self,
                             "sim",
                             _io,
                             _connectors,
                             toolchain="verilator")

    def create_programmer(self):
        raise ValueError("programming is not supported")


class BaseSoC(SoCCore):
    SoCCore.csr_map = {
        "ctrl": 0,  # provided by default (optional)
        "crg": 1,  # user
        "uart_phy": 2,  # provided by default (optional)
        "uart": 3,  # provided by default (optional)
        "identifier_mem": 4,  # provided by default (optional)
        "timer0": 5,  # provided by default (optional)
        "cpu_or_bridge": 8,
        "usb": 9,
        "picorvspi": 10,
        "touch": 11,
        "reboot": 12,
        "rgb": 13,
        "version": 14,
    }

    SoCCore.mem_map = {
        "rom": 0x00000000,  # (default shadow @0x80000000)
        "sram": 0x10000000,  # (default shadow @0xa0000000)
        "spiflash": 0x20000000,  # (default shadow @0xa0000000)
        "main_ram": 0x40000000,  # (default shadow @0xc0000000)
        "csr": 0x60000000,  # (default shadow @0xe0000000)
    }

    interrupt_map = {
        "usb": 3,
    }
    interrupt_map.update(SoCCore.interrupt_map)

    def __init__(self, platform, **kwargs):
        clk_freq = int(48e6)
        self.submodules.crg = _CRG(platform)
        output_dir = kwargs.get("output_dir", "build")
        usb_variant = kwargs.get("variant", "epfifo")
        kwargs['cpu_reset_address'] = 0x0

        self.output_dir = output_dir

        SoCCore.__init__(self,
                         platform,
                         clk_freq=clk_freq,
                         integrated_sram_size=0x8000,
                         with_uart=False,
                         **kwargs)
        self.integrated_rom_size = bios_size = 0x8000
        self.submodules.rom = wishbone.SRAM(bios_size, read_only=True, init=[])
        self.register_rom(self.rom.bus, bios_size)
        # Add USB pads
        usb_pads = platform.request("usb")
        usb_iobuf = usbio.IoBuf(usb_pads.d_p, usb_pads.d_n, usb_pads.pullup)
        self.comb += usb_pads.tx_en.eq(usb_iobuf.usb_tx_en)
        self.submodules.usb = epfifo.PerEndpointFifoInterface(usb_iobuf,
                                                              debug=False)
        class _WishboneBridge(Module):
            def __init__(self, interface):
                self.wishbone = interface

        spi_pads = platform.request("spiflash")
        self.submodules.picorvspi = PicoRVSpi(platform, spi_pads)
        self.register_mem("spiflash", self.mem_map["spiflash"],
            self.picorvspi.bus, size=self.picorvspi.size)
        self.submodules.wishbone = _WishboneBridge(
            self.platform.request("wishbone"))

def add_fsm_state_names():
    """Hack the FSM module to add state names to the output"""
    from migen.fhdl.visit import NodeTransformer
    from migen.genlib.fsm import NextState, NextValue, _target_eq
    from migen.fhdl.bitcontainer import value_bits_sign

    class My_LowerNext(NodeTransformer):
        def __init__(self, next_state_signal, next_state_name_signal, encoding,
                     aliases):
            self.next_state_signal = next_state_signal
            self.next_state_name_signal = next_state_name_signal
            self.encoding = encoding
            self.aliases = aliases
            # (target, next_value_ce, next_value)
            self.registers = []

        def _get_register_control(self, target):
            for x in self.registers:
                if _target_eq(target, x[0]):
                    return x[1], x[2]
            raise KeyError

        def visit_unknown(self, node):
            if isinstance(node, NextState):
                try:
                    actual_state = self.aliases[node.state]
                except KeyError:
                    actual_state = node.state
                return [
                    self.next_state_signal.eq(self.encoding[actual_state]),
                    self.next_state_name_signal.eq(
                        int.from_bytes(actual_state.encode(), byteorder="big"))
                ]
            elif isinstance(node, NextValue):
                try:
                    next_value_ce, next_value = self._get_register_control(
                        node.target)
                except KeyError:
                    related = node.target if isinstance(node.target,
                                                        Signal) else None
                    next_value = Signal(bits_sign=value_bits_sign(node.target),
                                        related=related)
                    next_value_ce = Signal(related=related)
                    self.registers.append(
                        (node.target, next_value_ce, next_value))
                return next_value.eq(node.value), next_value_ce.eq(1)
            else:
                return node

    import migen.genlib.fsm as fsm

    def my_lower_controls(self):
        self.state_name = Signal(len(max(self.encoding, key=len)) * 8,
                                 reset=int.from_bytes(
                                     self.reset_state.encode(),
                                     byteorder="big"))
        self.next_state_name = Signal(len(max(self.encoding, key=len)) * 8,
                                      reset=int.from_bytes(
                                          self.reset_state.encode(),
                                          byteorder="big"))
        self.comb += self.next_state_name.eq(self.state_name)
        self.sync += self.state_name.eq(self.next_state_name)
        return My_LowerNext(self.next_state, self.next_state_name,
                            self.encoding, self.state_aliases)

    fsm.FSM._lower_controls = my_lower_controls


def main():
    parser = argparse.ArgumentParser(
        description="Build test file for dummy or eptri module")
    builder_args(parser)
    soc_core_args(parser)
    parser.add_argument(
        '--variant',
        metavar='VARIANT',
        choices=['dummy', 'eptri', 'epfifo'],
        default='dummy',
        help='USB variant. Choices: [%(choices)s] (default: %(default)s)')
    parser.add_argument('--dir',
                        metavar='DIRECTORY',
                        default='build',
                        help='Output directory (defauilt: %(default)s)')
    parser.add_argument('--csr',
                        metavar='CSR',
                        default='csr.csv',
                        help='csr file (default: %(default)s)')
    parser.add_argument(
        "--bios_file",
        help="use specified file as a BIOS, rather than building one"
    )
    parser.add_argument("--ram-init", default=None, help="ram_init file")
    args = parser.parse_args()

    soc_kwargs = soc_core_argdict(args)
    if args.ram_init is not None:
        soc_kwargs["integrated_main_ram_init"] = \
            get_mem_data(args.ram_init, endianness='little')

    add_fsm_state_names()
    output_dir = args.dir

    platform = Platform()
    soc = BaseSoC(platform, **soc_kwargs)
    builder = Builder(soc,
                      output_dir=args.dir,
                      csr_csv=args.csr,
                      compile_software=True)
    builder.software_packages = [
        ("bios", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../foboot", "sw")))
    ]
    vns = builder.build(run=False)
    soc.do_exit(vns)

    print("""Simulation build complete.  Output files:
    {}/gateware/dut.v               Source Verilog file. Run this under Cocotb.
""".format(output_dir))


if __name__ == "__main__":
    main()
