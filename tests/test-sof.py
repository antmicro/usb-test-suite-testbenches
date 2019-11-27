
from os import environ

import cocotb
from cocotb.utils import get_sim_time
from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.usb.endpoint import EndpointType
from cocotb_usb.usb.pid import PID
from cocotb_usb.descriptors import Descriptor, getDescriptorRequest


descriptorFile = environ['TARGET_CONFIG']
model = UsbDevice(descriptorFile)


@cocotb.test()
def test_sof_stuffing(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

    yield harness.host_send_sof(0x04ff)
    yield harness.host_send_sof(0x0512)
    yield harness.host_send_sof(0x06e1)
    yield harness.host_send_sof(0x0519)


@cocotb.test()
def test_sof_is_ignored(dut):
    harness = get_harness(dut)
    harness.max_packet_size = model.deviceDescriptor.bMaxPacketSize0
    yield harness.reset()
    yield harness.wait(1e3, units="us")

    yield harness.port_reset(10e3)
    yield harness.connect()
    yield harness.wait(1e3, units="us")
    # After waiting (bus inactivity) let's start with SOF
    yield harness.host_send_sof(0x01)

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
