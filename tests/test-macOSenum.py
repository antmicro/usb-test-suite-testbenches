import cocotb
from cocotb.clock import Timer

from cocotb_usb.harness import get_harness
from cocotb_usb.device import UsbDevice
from cocotb_usb.descriptors import Descriptor

from os import environ

descriptorFile = environ['TARGET_CONFIG']

DEVICE_ADDRESS = 5

model = UsbDevice(descriptorFile)


@cocotb.test()
def test_macos_enumeration(dut):
    harness = get_harness(dut)
    yield harness.reset()
    yield harness.connect()

    yield Timer(1e3, units="us")

# [        ]   6.354863 d=  0.000000 [140.5 + 88.867] [ 11] DATA0: 23 03 04 00 03 00 00 00 cf 39
# [        ]   6.377496 d=  0.000000 [163.2 + 93.933] [ 11] DATA0: 23 01 14 00 03 00 00 00 ee 69
    yield harness.port_reset(20e3)  # 20 ms
# [        ]   6.400030 d=  0.000000 [185.7 +  0.800] [ 11] DATA0: 00 05 0d 00 00 00 00 00 eb e9
    yield harness.set_device_address(DEVICE_ADDRESS)
# [        ]   6.402629 d=  0.000000 [188.3 + 99.033] [ 11] DATA0: 80 06 00 01 00 00 12 00 e0 f4
    yield harness.get_device_descriptor(response=model.deviceDescriptor.get())
# [        ]   6.402953 d=  0.000000 [188.6 + 48.267] [ 11] DATA0: 80 06 02 03 09 04 02 00 d7 4b
    # Get first two bytes (to get length?)
    yield harness.get_string_descriptor(
        lang_id=Descriptor.LangId.ENG,
        idx=2,
        length=2,
        response=model.stringDescriptor[Descriptor.LangId.ENG][2].get()[:2])
# [        ]   6.403353 d=  0.000000 [189.1 + 72.650] [ 11] DATA0: 80 06 02 03 09 04 28 00 c8 2b
    # Read whole descriptor
    yield harness.get_string_descriptor(
        lang_id=Descriptor.LangId.ENG,
        idx=2,
        length=28,
        response=model.stringDescriptor[Descriptor.LangId.ENG][2].get()[:28])
# [        ]   6.404018 d=  0.000000 [189.6 +112.450] [ 11] DATA0: 80 06 01 03 09 04 02 00 d7 78
# Get idx 1, 2 bytes
    yield harness.get_string_descriptor(
        lang_id=Descriptor.LangId.ENG,
        idx=1,
        length=2,
        response=model.stringDescriptor[Descriptor.LangId.ENG][1].get()[:2])
# [        ]   6.404469 d=  0.000000 [190.2 + 63.650] [ 11] DATA0: 80 06 01 03 09 04 10 00 db d8
    yield harness.get_string_descriptor(
        lang_id=Descriptor.LangId.ENG,
        idx=1,
        length=0x10,
        response=model.stringDescriptor[Descriptor.LangId.ENG][2].get())
# [        ]   6.405033 d=  0.000000 [190.7 +  3.050] [ 11] DATA0: 80 06 03 03 09 04 02 00 d6 9a
    # Get idx 3 2 bytes
    yield harness.get_string_descriptor(
        lang_id=Descriptor.LangId.ENG,
        idx=3,
        length=2,
        response=model.stringDescriptor[Descriptor.LangId.ENG][1].get()[:2])
# [        ]   6.405550 d=  0.000000 [191.3 + 19.500] [ 11] DATA0: 80 06 03 03 09 04 1a 00 dc 9a
# Read whole
    yield harness.get_string_descriptor(
        lang_id=Descriptor.LangId.ENG,
        idx=3,
        length=0x1a,
        response=model.stringDescriptor[Descriptor.LangId.ENG][2].get())
#[        ]   0.447607 d=  0.000000 [ 75.3 +116.100] [ 11] DATA0: a3 00 00 00 03 00 04 00 f7 1d
#d->H CLASS recipient:other

# [        ]   6.407564 d=  0.000000 [193.3 + 33.733] [ 11] DATA0: 80 06 00 02 00 00 09 00 ae 04
    yield harness.get_configuration_descriptor(
        length=9,
        # Device must implement at least one configuration
        response=model.configDescriptor[1].get()[:9])
# [        ]   6.407821 d=  0.000000 [193.5 + 40.067] [ 11] DATA0: 80 06 00 02 00 00 20 00 b1 94
    total_config_len = model.configDescriptor[1].wTotalLength
    yield harness.get_configuration_descriptor(
        length=total_config_len,
        response=model.configDescriptor[1].get()[:total_config_len])
# [        ]   6.409208 d=  0.000000 [195.0 + 52.683] [ 11] DATA0: 00 09 01 00 00 00 00 00 27 25
    yield harness.set_configuration(1)
    # Device is in CONFIGURED state now

#[        ]   0.191106 d=  0.000000 [ 75.0 + 22.300] [ 11] DATA0: 00 03 01 00 00 00 00 00 8d 25
#SET FEATURE REMOTE WAKEUP

    # TODO: Class-specific config
