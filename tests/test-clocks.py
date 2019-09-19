from os import environ

import cocotb
from cocotb.clock import Clock

from cocotb_usb.host import UsbTestValenty
from cocotb_usb.device import UsbDevice
from cocotb_usb.clocks import UnstableClock

DESCRIPTOR_FILE = environ['TARGET_CONFIG']

DUT_CSRS = 'csr.csv'

model = UsbDevice(DESCRIPTOR_FILE)

@cocotb.test()
def test_accurate(dut):
    device_clock = Clock(dut.clk48_device, 20830, 'ps')
    cocotb.fork(device_clock.start())

    harness = UsbTestValenty(dut, DUT_CSRS)

    yield harness.reset()
    yield harness.connect()

    yield harness.get_device_descriptor(model.deviceDescriptor.get())

@cocotb.test()
def test_drift(dut):
    device_clock = Clock(dut.clk48_device, 20830+6, 'ps')
    cocotb.fork(device_clock.start())

    harness = UsbTestValenty(dut, DUT_CSRS, decouple_clocks=True)

    yield harness.reset()
    yield harness.connect()

    yield harness.get_device_descriptor(model.deviceDescriptor.get())

@cocotb.test()
def test_jitter(dut):
    device_clock = UnstableClock(dut.clk48_device, 20830, 3500, 3500, 'ps')
    cocotb.fork(device_clock.start())

    harness = UsbTestValenty(dut, DUT_CSRS, decouple_clocks=True)

    yield harness.reset()
    yield harness.connect()

    yield harness.get_device_descriptor(model.deviceDescriptor.get())
