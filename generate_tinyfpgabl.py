#!/usr/bin/env python3
# This script generates dut.v file for testing TinyFPGA Bootloader

# Disable pylint's E1101, which breaks completely on migen
#pylint:disable=E1101

from migen import Module, Signal, Instance, ClockDomain, If
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.fhdl.specials import TSTriple
from migen.fhdl.bitcontainer import bits_for
from migen.fhdl.structure import ClockSignal, ResetSignal, Replicate, Cat
from migen.genlib.cdc import MultiReg

from litex.build.generic_platform import Pins, IOStandard, Misc, Subsignal
from litex.soc.integration import SoCCore
from litex.soc.integration.builder import Builder
from litex.soc.integration.soc_core import csr_map_update
from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import AutoCSR, CSRStatus, CSRStorage

from platform_dut import *
import argparse
import os

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
        "uart_phy":       2,  # provided by default (optional)
        "uart":           3,  # provided by default (optional)
        "identifier_mem": 4,  # provided by default (optional)
        "timer0":         5,  # provided by default (optional)
        "cpu_or_bridge":  8,
        "usb":            9,
        "picorvspi":      10,
        "touch":          11,
        "reboot":         12,
        "rgb":            13,
        "version":        14,
    }

    SoCCore.mem_map = {
        "rom":      0x00000000,  # (default shadow @0x80000000)
        "sram":     0x10000000,  # (default shadow @0xa0000000)
        "spiflash": 0x20000000,  # (default shadow @0xa0000000)
        "main_ram": 0x40000000,  # (default shadow @0xc0000000)
        "csr":      0x60000000,  # (default shadow @0xe0000000)
    }

    interrupt_map = {
        "usb": 3,
    }
    interrupt_map.update(SoCCore.interrupt_map)

    def __init__(self, platform, output_dir="build", usb_variant='dummy', **kwargs):
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
        usb_pullup = Signal() # 1

        usb_p_t = TSTriple()
        usb_n_t = TSTriple()

        usb_pads = platform.request("usb")

        # Assign signals to triple
        usb_p_t_i = Signal()
        usb_n_t_i = Signal()
        self.specials += [
            MultiReg(usb_p_t.i, usb_p_t_i),
            MultiReg(usb_n_t.i, usb_n_t_i)
        ]
        self.comb += [
            If(usb_tx_en,
                usb_p_rx.eq(0b1),
                usb_n_rx.eq(0b0),
            ).Else(
                usb_p_rx.eq(usb_p_t_i),
                usb_n_rx.eq(usb_n_t_i),
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
                                    i_clk_48mhz = self.crg.cd_usb_48.clk,
                                    i_clk = self.crg.cd_sys.clk,
                                    i_reset = self.crg.cd_sys.rst,
                                    # USB lines
                                    o_usb_p_tx = usb_p_tx,
                                    o_usb_n_tx = usb_n_tx,
                                    i_usb_p_rx = usb_p_rx,
                                    i_usb_n_rx = usb_n_rx,
                                    o_usb_tx_en = usb_tx_en
                                    )


        class _WishboneBridge(Module):
            def __init__(self, interface):
                self.wishbone = interface

        self.add_cpu(_WishboneBridge(self.platform.request("wishbone")))
        self.add_wb_master(self.cpu.wishbone)

def add_fsm_state_names():
    """Hack the FSM module to add state names to the output"""
    from migen.fhdl.visit import NodeTransformer
    from migen.genlib.fsm import NextState, NextValue, _target_eq
    from migen.fhdl.bitcontainer import value_bits_sign

    class My_LowerNext(NodeTransformer):
        def __init__(self, next_state_signal, next_state_name_signal, encoding, aliases):
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
                    self.next_state_name_signal.eq(int.from_bytes(actual_state.encode(), byteorder="big"))
                ]
            elif isinstance(node, NextValue):
                try:
                    next_value_ce, next_value = self._get_register_control(node.target)
                except KeyError:
                    related = node.target if isinstance(node.target, Signal) else None
                    next_value = Signal(bits_sign=value_bits_sign(node.target), related=related)
                    next_value_ce = Signal(related=related)
                    self.registers.append((node.target, next_value_ce, next_value))
                return next_value.eq(node.value), next_value_ce.eq(1)
            else:
                return node
    import migen.genlib.fsm as fsm
    def my_lower_controls(self):
        self.state_name = Signal(len(max(self.encoding,key=len))*8, reset=int.from_bytes(self.reset_state.encode(), byteorder="big"))
        self.next_state_name = Signal(len(max(self.encoding,key=len))*8, reset=int.from_bytes(self.reset_state.encode(), byteorder="big"))
        self.comb += self.next_state_name.eq(self.state_name)
        self.sync += self.state_name.eq(self.next_state_name)
        return My_LowerNext(self.next_state, self.next_state_name, self.encoding, self.state_aliases)
    fsm.FSM._lower_controls = my_lower_controls

def generate(output_dir, csr_csv, variant):
    platform = Platform()
    soc = BaseSoC(platform, usb_variant=variant,
                            cpu_type=None, cpu_variant=None,
                            output_dir=output_dir)
    builder = Builder(soc, output_dir=output_dir,
                           csr_csv=csr_csv,
                           compile_software=False)
    vns = builder.build(run=False)
    soc.do_exit(vns)

def main():
    parser = argparse.ArgumentParser(
        description="Build test file for dummy or eptri module")
    parser.add_argument('variant', metavar='VARIANT',
                                   choices=['dummy', 'eptri', 'epfifo'],
                                   default='dummy',
                                   help='USB variant. Choices: [%(choices)s] (default: %(default)s)' )
    parser.add_argument('--dir', metavar='DIRECTORY',
                                 default='build',
                                 help='Output directory (defauilt: %(default)s)' )
    parser.add_argument('--csr', metavar='CSR',
                                 default='csr.csv',
                                 help='csr file (default: %(default)s)')
    args = parser.parse_args()
    add_fsm_state_names()
    output_dir = args.dir
    generate(output_dir, args.csr, args.variant)

    print(
"""Simulation build complete.  Output files:
    {}/gateware/dut.v               Source Verilog file.  Run this under Cocotb.
""".format(output_dir))

if __name__ == "__main__":
    main()
