import asyncio
import configparser
import os
import logging
import json

from bleak import BleakScanner
from bleak.assigned_numbers import AdvertisementDataType
from bleak.backends.bluezdbus.advertisement_monitor import OrPattern
from bleak.backends.bluezdbus.scanner import BlueZScannerArgs
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.uuids import normalize_uuid_16
from parser import BleParser
from bthome import parse_bthome

BTHOME_VID = 0xFCD2

log_level = os.getenv("LOG_LEVEL", "WARNING")
log_level = log_level.upper()
logger = logging.getLogger()

if hasattr(logging, log_level):
    logger.setLevel(getattr(logging, log_level))
else:
    logger.setLevel(logging.WARNING)

config = configparser.ConfigParser()
config.read("config.ini")

MAC_FILTER_CONTROL = config.getboolean("Main", "filter_mac_address")
MAC_ADDR_LIST = config.get("Main", "address_list").split(",")


def adv_callback(device: BLEDevice, advertisement_data: AdvertisementData):
    if normalize_uuid_16(BTHOME_VID) in advertisement_data.service_uuids:
        logger.info(
            f"{device.address} RSSI: {advertisement_data.rssi}, {advertisement_data}"
        )
        if device.address in MAC_ADDR_LIST or not MAC_FILTER_CONTROL:
            data = b"\x00\x00\x00\x00" + advertisement_data.service_data.get(
                normalize_uuid_16(BTHOME_VID)
            )
            # convert MAC address string for BTHome parser, which expects a bytes object
            mac_bytearray = bytes.fromhex(device.address.replace(":", ""))
            # try to retrieve encryption key from config file
            encryption_key = None
            key_str = config.get(
                "Encryption", device.address.replace(":", "").upper(), fallback=None
            )
            if key_str is not None:
                logger.info(f"Encryption key for {device.address} found")
                encryption_key = bytes.fromhex(key_str)
            # create parser with key
            parser = BleParser(aeskeys={mac_bytearray: encryption_key})
            sensor_data = parse_bthome(
                parser,
                data,
                BTHOME_VID,
                mac_bytearray,
            )
            if sensor_data is not None:
                data_callback(sensor_data)
            else:
                logger.info(
                    f"Failed to decode data from {device.address} {advertisement_data.local_name}"
                )


def data_callback(sensor_data):
    print(json.dumps(sensor_data))


async def main():
    passive_filters = [
        OrPattern(0, AdvertisementDataType.SERVICE_DATA_UUID16, b"\xd2\xfc"),
    ]

    scanner = BleakScanner(
        detection_callback=adv_callback,
        scanning_mode="passive",
        bluez=BlueZScannerArgs(or_patterns=passive_filters),
    )

    logger.info(f"MAC filter {"enabled" if MAC_FILTER_CONTROL else "disabled"}")
    if MAC_FILTER_CONTROL:
        logger.info(f"MAC address list: {MAC_ADDR_LIST}")
    await scanner.start()
    event = asyncio.Event()
    await event.wait()  # wait indefinitely


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )
    asyncio.run(main())
