# Generalized version of test-eptri script

from os import environ

import cocotb
from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.usb.endpoint import *
from cocotb_usb.usb.pid import *
from cocotb_usb.usb.descriptors import *

descriptorFile = environ['TARGET_CONFIG']
model = UsbDevice(descriptorFile)

@cocotb.test()
def test_control_setup(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    # Device is at address 0 after reset
    yield harness.transaction_setup(0,
            getDescriptorRequest(Descriptor.Types.DEVICE,
                descriptor_index=0,
                lang_id=0,
                length=0))
    yield harness.transaction_data_in(0, 0, [])

@cocotb.test()
def test_control_transfer_in(dut):
    harness = get_harness(dut)
    yield harness.reset()

    yield harness.connect()
    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS)
    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        getDescriptorRequest(descriptor_type=Descriptor.Types.STRING,
            descriptor_index=0,
            lang_id=0,
            length=10),
        model.stringDescriptorZero.get()
    )

@cocotb.test()
def test_sof_stuffing(dut):
    harness = get_harness(dut)
    yield harness.reset()

    yield harness.connect()
    yield harness.host_send_sof(0x04ff)
    yield harness.host_send_sof(0x0512)
    yield harness.host_send_sof(0x06e1)
    yield harness.host_send_sof(0x0519)


@cocotb.test()
def test_sof_is_ignored(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    DEVICE_ADDRESS = 0x20
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    epaddr_in = EndpointType.epaddr(0, EndpointType.IN)
    yield harness.set_device_address(DEVICE_ADDRESS)

    data = [0, 1, 8, 0, 4, 3, 0, 0]
    # Send SOF packet
    yield harness.host_send_sof(2)

    # Setup stage
    # ------------------------------------------
    # Send SETUP packet
    yield harness.host_send_token_packet(PID.SETUP, DEVICE_ADDRESS, EndpointType.epnum(epaddr_out))

    # Send another SOF packet
    yield harness.host_send_sof(3)

    # Data stage
    # ------------------------------------------
    # Send DATA packet
    yield harness.host_send_data_packet(PID.DATA1, data)
    yield harness.host_expect_ack()

    # Send another SOF packet
    yield harness.host_send_sof(4)

    # # Status stage
    # # ------------------------------------------
    yield harness.transaction_status_out(DEVICE_ADDRESS, epaddr_out)

@cocotb.test()
def test_control_setup_clears_stall(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    addr = 0
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)

    d = [0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0, 0]

    # send the data -- just to ensure that things are working
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # send it again to ensure we can re-queue things.
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # Set endpoint HALT explicitly
    yield harness.control_transfer_out(0,
            setFeatureRequest(FeatureSelector.ENDPOINT_HALT, USBDeviceRequest.Type.ENDPOINT, 0),
            None
            )

    # do another receive, which should fail
    yield harness.transaction_data_out(addr, epaddr_out, d, expected=PID.STALL)

    # do a setup, which should pass
    yield harness.control_transfer_out(addr, d)

    # finally, do one last transfer, which should succeed now
    # that the endpoint is unstalled.
    yield harness.transaction_data_out(addr, epaddr_out, d)

@cocotb.test()
def test_control_transfer_in_out(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
            descriptor_index=0,
            lang_id=0,
            length=0x40),
        model.deviceDescriptor.get()
    )

    yield harness.set_device_address(11) # This utilizes an OUT control transfer

@cocotb.test()
def test_control_transfer_in_out_in(dut):
    """This transaction is pretty much the first thing any OS will do"""
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    device_address = 0 # After reset
    yield harness.control_transfer_in(
        device_address,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
            descriptor_index=0,
            lang_id=0,
            length=0x40),
        model.deviceDescriptor.get()
    )

    device_address = 11
    yield harness.set_device_address(device_address) # This utilizes an OUT control transfer

    yield harness.control_transfer_in(
        device_address,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
            descriptor_index=0,
            lang_id=0,
            length=0x40),
        model.deviceDescriptor.get()
    )

@cocotb.test()
def test_control_transfer_out_in(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS) # This utilizes an OUT control transfer

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        # Get device descriptor
        getDescriptorRequest(Descriptor.Types.DEVICE,
            descriptor_index=0,
            lang_id=0,
            length=0x40),
        model.deviceDescriptor.get()
    )

