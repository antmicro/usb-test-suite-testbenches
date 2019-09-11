import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, NullTrigger, Timer
from cocotb.result import TestFailure, TestSuccess, ReturnValue

from cocotb_usb.host_valenty import UsbTestValenty
from cocotb_usb.utils import grouper_tofit
from cocotb_usb.usb.endpoint import *
from cocotb_usb.usb.pid import *
from cocotb_usb.usb.descriptors import *

dut_csrs = 'csr.csv'
DEVICE_ADDRESS = 20

@cocotb.coroutine
def get_device_descriptor(harness):
    # Device has no address set yet
    DEVICE_ADDRESS_UNINITIALIZED = 0
    yield harness.write(harness.csrs['usb_address'], DEVICE_ADDRESS_UNINITIALIZED)

    # Set address (to 20)
    yield harness.control_transfer_out(
        DEVICE_ADDRESS_UNINITIALIZED,
        setAddressRequest(DEVICE_ADDRESS),
        None,
    )

    yield harness.write(harness.csrs['usb_address'], DEVICE_ADDRESS)

    device_descriptor_request = getDescriptorRequest(descriptor_type = Descriptor.Types.DEVICE,
            descriptor_index = 0,
            lang_id = Descriptor.LangId.UNSPECIFIED,
            length = 10)

    device_descriptor_response = DeviceDescriptor.build(bLength=18,
            bDescriptorType=Descriptor.Types.DEVICE,
            bcdUSB = 0x0200,
            bDeviceClass = 0x00,
            bDeviceSubClass = 0x00,
            bDeviceProtocol = 0x00,
            bMaxPacketSize0 = 0x40,
            idVendor = 0x1d6b,
            idProduct = 0x0105,
            bcdDevice = 0x0100,
            iManufacturer = 0x01,
            iProduct = 0x02,
            iSerialNumber = 0x03,
            bNumConfigurations = 0x01)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        device_descriptor_request,
        device_descriptor_response,
    )

@cocotb.coroutine
def get_configuration_descriptor(harness):
    config_descriptor_request = getDescriptorRequest(descriptor_type = Descriptor.Types.CONFIGURATION,
            descriptor_index = 0,
            lang_id = Descriptor.LangId.UNSPECIFIED,
            length = 9)

    config_descriptor_response = ConfigDescriptor.build(bLength = 9,
            wTotalLength = 32,
            bNumInterfaces = 1,
            bConfigurationValue = 0x01,
            iConfiguration = 0,
            bmAttributes = ConfigDescriptor.Attributes.NONE,
            bMaxPower = 50)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        config_descriptor_request,
        config_descriptor_response,
    )

@cocotb.coroutine
def get_string_descriptor(harness):
    # Get LangId list
    string_descriptor_request = getDescriptorRequest(descriptor_type = Descriptor.Types.STRING,
            descriptor_index = 0,
            lang_id = Descriptor.LangId.UNSPECIFIED,
            length = 255)
    string_descriptor_response = StringDescriptor.buildIdx0(wLangIdList = [0x0409])

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        string_descriptor_request,
        string_descriptor_response,
    )

    # Read a descriptor using received LangId
    string_descriptor_request = getDescriptorRequest(descriptor_type = Descriptor.Types.STRING,
            descriptor_index = 1,
            lang_id = Descriptor.LangId.ENG,
            length = 255)

    string_descriptor_response = StringDescriptor.build("Generic")
    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        string_descriptor_request,
        string_descriptor_response,
    )

@cocotb.coroutine
def set_configuration(harness):
    # Set configuration
    request = setConfigurationRequest(1)

    yield harness.control_transfer_out(
        DEVICE_ADDRESS,
        request,
        None,
    )
    # Device should now be in "Configured" state
    pass

@cocotb.test()
def test_enumeration(dut):
    harness = UsbTestValenty(dut, dut_csrs)
    yield harness.reset()
    yield harness.connect()

    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.OUT))
    yield harness.clear_pending(EndpointType.epaddr(0, EndpointType.IN))

    yield get_device_descriptor(harness)
    yield get_configuration_descriptor(harness)
    yield get_string_descriptor(harness)
    #TODO: Set configuration
    yield set_configuration(harness)
    #TODO: Class-specific config

