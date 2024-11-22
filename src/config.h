// SPDX-License-Identifier: Apache-2.0

#define SLEEP_TIMEOUT_SEC  10
#define DEBOUNCE_TIMER_SEC 1

extern const struct gpio_dt_spec occupancy_sw;
extern const struct gpio_dt_spec vbus_det;
extern const struct gpio_dt_spec charge_status;
extern const struct device *const console;
