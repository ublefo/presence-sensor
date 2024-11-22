// SPDX-License-Identifier: Apache-2.0

void wait_on_log_flushed(void);
void switch_state_callback(const struct device *dev, struct gpio_callback *cb,
			   gpio_port_pins_t pins);
void charge_state_callback(const struct device *dev, struct gpio_callback *cb,
			   gpio_port_pins_t pins);
void sensor_update(void);
