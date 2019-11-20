# Generalized version of test-eptri script

from os import environ

import cocotb
from cocotb.clock import Timer
from cocotb.utils import get_sim_time
from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.usb.endpoint import EndpointType
from cocotb_usb.usb.pid import PID
from cocotb_usb.descriptors import (Descriptor, getDescriptorRequest,
                                    FeatureSelector, USBDeviceRequest,
                                    setFeatureRequest)

descriptorFile = environ['TARGET_CONFIG']
model = UsbDevice(descriptorFile)


@cocotb.test()
def test_control_setup(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()
    yield harness.port_reset(1e3)

    # Device is at address 0 after reset
    yield harness.transaction_setup(
        0,
        setFeatureRequest(FeatureSelector.ENDPOINT_HALT,
                          USBDeviceRequest.Type.ENDPOINT, 0))
    harness.packet_deadline = get_sim_time("us") + harness.MAX_PACKET_TIME
    yield harness.transaction_data_in(0, 0, [])


@cocotb.test()
def test_control_transfer_in(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()
    yield Timer(1e3, units="us")

    DEVICE_ADDRESS = 20
    yield harness.set_device_address(DEVICE_ADDRESS)
    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        getDescriptorRequest(descriptor_type=Descriptor.Types.DEVICE,
                             descriptor_index=1,
                             lang_id=0,
                             length=18), model.deviceDescriptor.get())


@cocotb.test()
def test_sof_stuffing(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()
    yield Timer(1e3, units="us")

    yield harness.host_send_sof(0x04ff)
    yield harness.host_send_sof(0x0512)
    yield harness.host_send_sof(0x06e1)
    yield harness.host_send_sof(0x0519)


@cocotb.test()
def test_sof_is_ignored(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()
    yield Timer(1e3, units="us")

    DEVICE_ADDRESS = 0x20
    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)
    yield harness.set_device_address(DEVICE_ADDRESS)

    data = getDescriptorRequest(descriptor_type=Descriptor.Types.STRING,
                                descriptor_index=0,
                                lang_id=0,
                                length=10)
    # Send SOF packet
    yield harness.host_send_sof(2)

    # Setup stage
    # ------------------------------------------
    # Send SETUP packet
    yield harness.host_send_token_packet(PID.SETUP, DEVICE_ADDRESS,
                                         EndpointType.epnum(epaddr_out))
    harness.request_deadline = get_sim_time("us") + harness.MAX_REQUEST_TIME

    # Send another SOF packet
    yield harness.host_send_sof(3)

    # Data stage
    # ------------------------------------------
    # Send DATA packet
    harness.packet_deadline = get_sim_time("us") + harness.MAX_PACKET_TIME
    yield harness.host_send_data_packet(PID.DATA1, data)
    yield harness.host_expect_ack()

    # Send another SOF packet
    yield harness.host_send_sof(4)

    # # Status stage
    # # ------------------------------------------
    harness.packet_deadline = get_sim_time("us") + harness.MAX_PACKET_TIME
    yield harness.transaction_status_out(DEVICE_ADDRESS, epaddr_out)


@cocotb.test(expect_fail=True)  # Doesn't set STALL as expected
def test_control_setup_clears_stall(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()
    yield Timer(1e3, units="us")

    addr = 13
    yield harness.set_device_address(addr)
    yield harness.set_configuration(1)
    yield Timer(1e2, units="us")

    epaddr_out = EndpointType.epaddr(0, EndpointType.OUT)

    d = [0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0, 0]

    # send the data -- just to ensure that things are working
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # send it again to ensure we can re-queue things.
    yield harness.transaction_data_out(addr, epaddr_out, d)

    # Set endpoint HALT explicitly
    yield harness.transaction_setup(
        addr,
        setFeatureRequest(FeatureSelector.ENDPOINT_HALT,
                          USBDeviceRequest.Type.ENDPOINT, 0))
    harness.packet_deadline = get_sim_time("us") + harness.MAX_PACKET_TIME
    yield harness.transaction_data_in(addr, 0, [])
    # do another receive, which should fail
    harness.retry = True
    harness.packet_deadline = get_sim_time("us") + 1e3  # try for a ms
    while harness.retry:
        yield harness.host_send_token_packet(PID.IN, addr, 0)
        yield harness.host_expect_stall()
        if get_sim_time("us") > harness.packet_deadline:
            raise cocotb.result.TestFailure("Did not receive STALL token")

    # do a setup, which should pass
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())

    # finally, do one last transfer, which should succeed now
    # that the endpoint is unstalled.
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())


@cocotb.test()
def test_control_transfer_in_out(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()
    yield Timer(1e3, units="us")

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
    yield harness.reset()
    yield harness.connect()
    yield Timer(1e3, units="us")

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
    yield harness.reset()
    yield harness.connect()
    yield Timer(1e3, units="us")

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
