from machine import Pin, I2C
import utime
import framebuf
import ssd1306

# OLED on I2C0
# SDA = GP0, SCL = GP1
i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Encoder 1 controls Y
E1_CLK_PIN = 2
E1_DT_PIN = 3
E1_SW_PIN = 4

# Encoder 2 controls X
E2_CLK_PIN = 5
E2_DT_PIN = 6
E2_SW_PIN = 7

e1_clk = Pin(E1_CLK_PIN, Pin.IN, Pin.PULL_UP)
e1_dt = Pin(E1_DT_PIN, Pin.IN, Pin.PULL_UP)
e1_sw = Pin(E1_SW_PIN, Pin.IN, Pin.PULL_UP)

e2_clk = Pin(E2_CLK_PIN, Pin.IN, Pin.PULL_UP)
e2_dt = Pin(E2_DT_PIN, Pin.IN, Pin.PULL_UP)
e2_sw = Pin(E2_SW_PIN, Pin.IN, Pin.PULL_UP)

# Full display is the drawing screen
DRAW_W = 128
DRAW_H = 64

# Persistent drawing canvas
canvas_buf = bytearray(DRAW_W * ((DRAW_H + 7) // 8))
canvas = framebuf.FrameBuffer(canvas_buf, DRAW_W, DRAW_H, framebuf.MONO_VLSB)
canvas.fill(0)

# Cursor starts in center
x = DRAW_W // 2
y = DRAW_H // 2
canvas.pixel(x, y, 1)
points = [(x, y, 0)]
redo_stack = []

# Movement-time clock (pauses while idle)
draw_time_ms = 0
last_move_real_ms = None
MAX_MOVE_GAP_MS = 150

last_clk1 = e1_clk.value()
last_clk2 = e2_clk.value()
last_btn1_ms = 0
last_btn2_ms = 0

dirty = True


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def mark_dirty():
    global dirty
    dirty = True


def render():
    oled.blit(canvas, 0, 0)

    # Cursor marker (small cross)
    oled.pixel(x, y, 1)
    if x > 0:
        oled.pixel(x - 1, y, 1)
    if x < DRAW_W - 1:
        oled.pixel(x + 1, y, 1)
    if y > 0:
        oled.pixel(x, y - 1, 1)
    if y < DRAW_H - 1:
        oled.pixel(x, y + 1, 1)

    oled.show()


def rebuild_canvas_from_points():
    canvas.fill(0)
    for px, py, _ in points:
        canvas.pixel(px, py, 1)


def step_cursor(dx, dy):
    global x, y, redo_stack, draw_time_ms, last_move_real_ms
    now = utime.ticks_ms()
    if last_move_real_ms is not None:
        dt = utime.ticks_diff(now, last_move_real_ms)
        if dt < 0:
            dt = 0
        draw_time_ms += dt if dt < MAX_MOVE_GAP_MS else MAX_MOVE_GAP_MS
    last_move_real_ms = now

    nx = clamp(x + dx, 0, DRAW_W - 1)
    ny = clamp(y + dy, 0, DRAW_H - 1)
    if nx != x or ny != y:
        x = nx
        y = ny
        canvas.pixel(x, y, 1)
        points.append((x, y, draw_time_ms))
        redo_stack = []
        mark_dirty()


def undo_last_two_seconds(now):
    global x, y, points
    del now
    kept = []
    removed = []
    for px, py, pt in points:
        if draw_time_ms - pt > 2000:
            kept.append((px, py, pt))
        else:
            removed.append((px, py, pt))

    if not removed:
        return

    if not kept:
        x = DRAW_W // 2
        y = DRAW_H // 2
        kept = [(x, y, draw_time_ms)]

    redo_stack.append(removed)
    x, y, _ = kept[-1]

    points = kept
    rebuild_canvas_from_points()
    mark_dirty()


def redo_last_undo():
    global x, y, points
    if not redo_stack:
        return

    restored = redo_stack.pop()
    points.extend(restored)
    x, y, _ = points[-1]
    rebuild_canvas_from_points()
    mark_dirty()


def on_rotate_1(pin):
    global last_clk1
    current_clk = e1_clk.value()

    # Y axis movement on falling edge for stable single-step behavior.
    if last_clk1 == 1 and current_clk == 0:
        if e1_dt.value() == 1:
            step_cursor(0, -1)
        else:
            step_cursor(0, 1)

    last_clk1 = current_clk


def on_rotate_2(pin):
    global last_clk2
    current_clk = e2_clk.value()

    # X axis movement on falling edge for stable single-step behavior.
    if last_clk2 == 1 and current_clk == 0:
        if e2_dt.value() == 1:
            step_cursor(1, 0)
        else:
            step_cursor(-1, 0)

    last_clk2 = current_clk


def on_button_1(pin):
    global last_btn1_ms
    now = utime.ticks_ms()
    if utime.ticks_diff(now, last_btn1_ms) > 200:
        print("UNDO")
        undo_last_two_seconds(now)
        last_btn1_ms = now


def on_button_2(pin):
    global last_btn2_ms
    now = utime.ticks_ms()
    if utime.ticks_diff(now, last_btn2_ms) > 200:
        print("REDO")
        redo_last_undo()
        last_btn2_ms = now


e1_clk.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=on_rotate_1)
e1_sw.irq(trigger=Pin.IRQ_FALLING, handler=on_button_1)

e2_clk.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=on_rotate_2)
e2_sw.irq(trigger=Pin.IRQ_FALLING, handler=on_button_2)

print("Wokwi drawing screen ready")

while True:
    if dirty:
        dirty = False
        render()
    utime.sleep_ms(20)
