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

from os import environ

descriptorFile = environ['TARGET_CONFIG']

dut_csrs = 'csr.csv'
DEVICE_ADDRESS = 20

model = UsbDevice(descriptorFile)

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

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        device_descriptor_request,
        model.deviceDescriptor.get()
    )

@cocotb.coroutine
def get_configuration_descriptor(harness):
    config_descriptor_request = getDescriptorRequest(descriptor_type = Descriptor.Types.CONFIGURATION,
            descriptor_index = 0,
            lang_id = Descriptor.LangId.UNSPECIFIED,
            length = 9)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        config_descriptor_request,
        model.configDescriptor[1].get()[:9]
    )

    # Since we got total length let's read the whole descriptor
    config_descriptor_request = getDescriptorRequest(descriptor_type = Descriptor.Types.CONFIGURATION,
            descriptor_index = 0,
            lang_id = Descriptor.LangId.UNSPECIFIED,
            length = model.configDescriptor[1].wTotalLength)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        config_descriptor_request,
        model.configDescriptor[1].get()
    )

@cocotb.coroutine
def get_string_descriptor(harness):
    # Get LangId list
    string_descriptor_request = getDescriptorRequest(descriptor_type = Descriptor.Types.STRING,
            descriptor_index = 0,
            lang_id = Descriptor.LangId.UNSPECIFIED,
            length = 255)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        string_descriptor_request,
        model.stringDescriptorZero.get()
    )

    # Read a descriptor using received LangId
    string_descriptor_request = getDescriptorRequest(descriptor_type = Descriptor.Types.STRING,
            descriptor_index = 1,
            lang_id = Descriptor.LangId.ENG,
            length = 255)

    yield harness.control_transfer_in(
        DEVICE_ADDRESS,
        string_descriptor_request,
        model.stringDescriptor[Descriptor.LangId.ENG][0].get()
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

