## Simple Presence Sensor

A simple battery powered presence sensor designed to run on a Particle Argon. The presence sensor is a simple switch which could be mounted on a seat or a door depending on your use case, sensor state and battery info are transmitted with BLE advertisements in the [BTHome v2](https://bthome.io/format/) format. After an inactivity timeout, the device will power off and wake up again when the sensor state changes.

Additionally, this project can also serve as a more comprehensive demo for how to set up a basic Zephyr project that uses interrupts, threads, Bluetooth advertisements and system off.

### Build

Follow the [getting started](https://docs.zephyrproject.org/4.0.0/develop/getting_started/index.html) page to set up a build environment, and run `west build -b particle_argon --pristine auto`.

### Hardware

- Particle Argon
- LiPo battery (2000mAh)
- Switch
- 100K resistor
- 0.1uF capacitor

Connect the switch between D8 and GND, with a 100K resistor between D8 and 3V3 for pull-up. Connect the 0.1uF capacitor in parallel with the switch for debouncing.

On the host side, you'll need a Bluetooth adapter. RTL8761B based dongles such as the UB500 should be reliable enough for passive scanning. While this device should work out of the box with HomeAssistant, a python script is also provided in case you don't want to use HomeAssistant.

### Power

The Particle Argon was selected because it is still widely available and is designed properly for low power use cases. The Adafruit Feather nRF52840 Express is unusable for this application due to the high quiescent current of the onboard NeoPixel LED. The ESP32 on the Particle Argon is kept powered down with a GPIO hog.

The internal pull-up in the nRF52840 is quite strong, so an external pull-up ressitor is required for optimal battery life. Pull-up for charge termination detection is only enabled when the device is running for the same reason.

With a 100K pull-up for the switch and 3.7V on the battery connector, the board consumes about 750 ~ 950uA when active, and around 82uA on average in system off state. A 2000mAh LiPo cell should be able to keep the device running for a few months.
