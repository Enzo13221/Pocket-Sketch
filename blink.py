from machine import Pin
import utime

# Encoder 1 pin mapping (Y axis)
E1_CLK_PIN = 2
E1_DT_PIN = 3
E1_SW_PIN = 4

# Encoder 2 pin mapping (X axis)
E2_CLK_PIN = 5
E2_DT_PIN = 6
E2_SW_PIN = 7

# Create pins (active-low with pull-ups)
e1_clk = Pin(E1_CLK_PIN, Pin.IN, Pin.PULL_UP)
e1_dt = Pin(E1_DT_PIN, Pin.IN, Pin.PULL_UP)
e1_sw = Pin(E1_SW_PIN, Pin.IN, Pin.PULL_UP)

e2_clk = Pin(E2_CLK_PIN, Pin.IN, Pin.PULL_UP)
e2_dt = Pin(E2_DT_PIN, Pin.IN, Pin.PULL_UP)
e2_sw = Pin(E2_SW_PIN, Pin.IN, Pin.PULL_UP)

# XY coordinate state
x = 0
y = 0

last_clk1 = e1_clk.value()
last_clk2 = e2_clk.value()
last_btn1_ms = 0
last_btn2_ms = 0


def print_xy():
    print("X:", x, "Y:", y)


def on_rotate_1(pin):
    global y, last_clk1
    current_clk = e1_clk.value()

    # Step once per detent edge to avoid double counting.
    if last_clk1 == 1 and current_clk == 0:
        if e1_dt.value() == 1:
            y += 1
        else:
            y -= 1
        print_xy()

    last_clk1 = current_clk


def on_rotate_2(pin):
    global x, last_clk2
    current_clk = e2_clk.value()

    # Step once per detent edge to avoid double counting.
    if last_clk2 == 1 and current_clk == 0:
        if e2_dt.value() == 1:
            x += 1
        else:
            x -= 1
        print_xy()

    last_clk2 = current_clk


def on_button_1(pin):
    global last_btn1_ms
    now = utime.ticks_ms()
    if utime.ticks_diff(now, last_btn1_ms) > 200:
        print("UNDO")
        last_btn1_ms = now


def on_button_2(pin):
    global last_btn2_ms
    now = utime.ticks_ms()
    if utime.ticks_diff(now, last_btn2_ms) > 200:
        print("REDO")
        last_btn2_ms = now


# IRQs
e1_clk.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=on_rotate_1)
e1_sw.irq(trigger=Pin.IRQ_FALLING, handler=on_button_1)

e2_clk.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=on_rotate_2)
e2_sw.irq(trigger=Pin.IRQ_FALLING, handler=on_button_2)

print("XY controller ready")
print_xy()

while True:
    utime.sleep_ms(100)
