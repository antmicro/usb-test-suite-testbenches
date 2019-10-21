import cocotb
from cocotb.clock import Timer

from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.descriptors import Descriptor

from os import environ

descriptorFile = environ['TARGET_CONFIG']

DEVICE_ADDRESS = 20

model = UsbDevice(descriptorFile)


@cocotb.test()
def test_enumeration(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    yield Timer(1e3, units="us")

    yield harness.port_reset(1e3)
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())

    yield harness.set_device_address(DEVICE_ADDRESS)
    yield harness.get_configuration_descriptor(
        length=9,
        # Device must implement at least one configuration
        response=model.configDescriptor[1].get()[:9])

    total_config_len = model.configDescriptor[1].wTotalLength
    yield harness.get_configuration_descriptor(
        length=total_config_len,
        response=model.configDescriptor[1].get()[:total_config_len])

    yield harness.get_string_descriptor(
        lang_id=Descriptor.LangId.UNSPECIFIED,
        idx=0,
        response=model.stringDescriptor[0].get())

    if model.stringDescriptor[0].wLangId:
        # If the device implements string descriptors, let's try reading them
        lang_id = model.stringDescriptor[0].wLangId[0]
        yield harness.get_string_descriptor(
            lang_id=lang_id,
            idx=1,
            response=model.stringDescriptor[lang_id][1].get())

    yield harness.set_configuration(1)
    # Device should now be in "Configured" state
    # TODO: Class-specific config
