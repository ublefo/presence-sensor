// SPDX-License-Identifier: Apache-2.0

#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>

#include "battery.h"
#include "bt.h"
#include "util.h"
#include "config.h"

LOG_MODULE_REGISTER(MAIN, LOG_LEVEL_INF);

const struct gpio_dt_spec occupancy_sw = GPIO_DT_SPEC_GET(DT_NODELABEL(occupancy_sw), gpios);
const struct gpio_dt_spec vbus_det = GPIO_DT_SPEC_GET(DT_NODELABEL(vbus_det), gpios);
const struct gpio_dt_spec charge_status = GPIO_DT_SPEC_GET(DT_NODELABEL(charge_status), gpios);

const struct device *const console = DEVICE_DT_GET(DT_CHOSEN(zephyr_console));

static struct gpio_callback switch_cb_data;
static struct gpio_callback vbus_det_cb_data;
static struct gpio_callback charge_status_cb_data;

int main(void)
{
	LOG_INF("Occupancy sensor application running on %s", CONFIG_BOARD);

	// GPIO config and interrupt setup
	gpio_pin_configure_dt(&occupancy_sw, GPIO_INPUT);
	gpio_pin_interrupt_configure_dt(&occupancy_sw, GPIO_INT_EDGE_BOTH);
	gpio_init_callback(&switch_cb_data, switch_state_callback, BIT(occupancy_sw.pin));
	gpio_add_callback(occupancy_sw.port, &switch_cb_data);

	gpio_pin_configure_dt(&vbus_det, GPIO_INPUT);
	gpio_pin_interrupt_configure_dt(&vbus_det, GPIO_INT_EDGE_BOTH);
	gpio_init_callback(&vbus_det_cb_data, charge_state_callback, BIT(vbus_det.pin));
	gpio_add_callback(vbus_det.port, &vbus_det_cb_data);

	// only enable pull-up at runtime
	gpio_pin_configure_dt(&charge_status, (GPIO_INPUT | GPIO_PULL_UP));
	gpio_pin_interrupt_configure_dt(&charge_status, GPIO_INT_EDGE_BOTH);
	gpio_init_callback(&charge_status_cb_data, charge_state_callback, BIT(charge_status.pin));
	gpio_add_callback(charge_status.port, &charge_status_cb_data);

	LOG_INF("Setup complete");

	advertising_start();
	sensor_update();

	return 0;
}
