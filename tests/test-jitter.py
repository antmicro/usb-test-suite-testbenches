import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, NullTrigger, Timer
from cocotb.result import TestFailure, TestSuccess, ReturnValue

from cocotb_usb.host import UsbTestValenty
from cocotb_usb.device import UsbDevice
from cocotb_usb.utils import grouper_tofit
from cocotb_usb.usb.endpoint import *
from cocotb_usb.usb.pid import *
from cocotb_usb.usb.descriptors import *
from cocotb_usb.clocks import UnstableClock

from os import environ

descriptorFile = environ['TARGET_CONFIG']

dut_csrs = 'csr.csv'
DEVICE_ADDRESS = 20

model = UsbDevice(descriptorFile)

@cocotb.test()
def test_accurate(dut):
    device_clock = Clock(dut.clk48_device, 20800, 'ps')
    cocotb.fork(device_clock.start())

    harness = UsbTestValenty(dut, dut_csrs)

    yield harness.reset()
    yield harness.connect()

    yield harness.get_device_descriptor(model.deviceDescriptor.get())

@cocotb.test()
def test_drift(dut):
    device_clock = Clock(dut.clk48_device, 20900, 'ps')
    cocotb.fork(device_clock.start())

    harness = UsbTestValenty(dut, dut_csrs)

    yield harness.reset()
    yield harness.connect()

    yield harness.get_device_descriptor(model.deviceDescriptor.get())

@cocotb.test()
def test_jitter(dut):
    device_clock = UnstableClock(dut.clk48_device, 20800, 1, 1, 'ps')
    cocotb.fork(device_clock.start())

    harness = UsbTestValenty(dut, dut_csrs)

    yield harness.reset()
    yield harness.connect()

    yield harness.get_device_descriptor(model.deviceDescriptor.get())

