from os import environ

import cocotb
from cocotb.clock import Clock

from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.clocks import UnstableClock

DESCRIPTOR_FILE = environ['TARGET_CONFIG']

model = UsbDevice(DESCRIPTOR_FILE)


@cocotb.test()
def test_accurate(dut):
    device_clock = Clock(dut.clk48_device, 20830, 'ps')
    cocotb.fork(device_clock.start())

    harness = get_harness(dut)

    yield harness.reset()
    yield harness.connect()

    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

    yield harness.get_device_descriptor(model.deviceDescriptor.get())


@cocotb.test()
def test_drift(dut):
    device_clock = Clock(dut.clk48_device, 20830 + 6, 'ps')
    cocotb.fork(device_clock.start())

    harness = get_harness(dut, decouple_clocks=True)

    yield harness.reset()
    yield harness.connect()

    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

    yield harness.get_device_descriptor(model.deviceDescriptor.get())


@cocotb.test()
def test_jitter(dut):
    device_clock = UnstableClock(dut.clk48_device, 20830, 3500, 3500, 'ps')
    cocotb.fork(device_clock.start())

    harness = get_harness(dut, decouple_clocks=True)

    yield harness.reset()
    yield harness.connect()

    yield harness.wait(1e3, units="us")
    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

    yield harness.get_device_descriptor(model.deviceDescriptor.get())
