
from os import environ

import cocotb
from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.descriptors import Descriptor, getDescriptorRequest

descriptorFile = environ['TARGET_CONFIG']
model = UsbDevice(descriptorFile)


@cocotb.test()
def test_control_transfer_in_out(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
                             descriptor_index=0,
                             lang_id=0,
                             length=0x40),
        model.deviceDescriptor.get())

    yield harness.set_device_address(
        11)  # This utilizes an OUT control transfer


@cocotb.test()
def test_control_transfer_in_out_in(dut):
    """This transaction is pretty much the first thing any OS will do"""
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

    device_address = 0  # After reset
    yield harness.control_transfer_in(
        device_address,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
                             descriptor_index=0,
                             lang_id=0,
                             length=0x40),
        model.deviceDescriptor.get())

    device_address = 11
    yield harness.set_device_address(
        device_address)  # This utilizes an OUT control transfer

    yield harness.control_transfer_in(
        device_address,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
                             descriptor_index=0,
                             lang_id=0,
                             length=0x40),
        model.deviceDescriptor.get())


@cocotb.test()
def test_control_transfer_out_in(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

    DEVICE_ADDRESS = 20
    yield harness.set_device_address(
        DEVICE_ADDRESS)  # This utilizes an OUT control transfer

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
                             descriptor_index=0,
                             lang_id=0,
                             length=0x40),
        model.deviceDescriptor.get())
