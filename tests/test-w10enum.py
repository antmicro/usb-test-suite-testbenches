from os import environ

import cocotb
from cocotb.clock import Clock, Timer
from cocotb.triggers import RisingEdge
from cocotb.result import TestFailure, TestSuccess, ReturnValue

from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.usb.descriptors import *


DESCRIPTOR_FILE = environ['TARGET_CONFIG']

DEVICE_ADDRESS = 5
model = UsbDevice(DESCRIPTOR_FILE)

@cocotb.test()
def test_enumeration_w10(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()
    yield Timer(1e3, units="us");

    yield harness.port_reset(1e3)
    yield harness.get_device_descriptor(length=0x40, response=model.deviceDescriptor.get())
    yield harness.port_reset(1e3)

    yield harness.set_device_address(DEVICE_ADDRESS)
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())
    yield harness.get_configuration_descriptor(length=0xFF, response=model.configDescriptor[1].get())

    # Get device qualifier - for USB 2.0 devices only!
    #yield harness.get_device_qualifier(length=0x0A, response=model.deviceQualifierDescriptor.get()[:10])

    yield harness.get_device_descriptor(length=0x12, response=model.deviceDescriptor.get()[:0x12])
    yield harness.get_configuration_descriptor(length=0x09, response=model.configDescriptor[1].get()[:9])

    # Read whole Configuration Descriptor
    total_length = model.configDescriptor[1].wTotalLength
    yield harness.get_configuration_descriptor(total_length, response=model.configDescriptor[1].get())
    #NOTE Why exactly 265 bytes are requested below?
    yield harness.get_configuration_descriptor(length=0x0109, response=model.configDescriptor[1].get())

    yield harness.set_configuration(1)

    # *** Start of class-specific config ***
