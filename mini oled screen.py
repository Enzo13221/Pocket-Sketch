from machine import Pin, I2C
import utime
import framebuf
from micropython import const

SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xA0)
SET_MUX_RATIO = const(0xA8)
SET_COM_OUT_DIR = const(0xC0)
SET_DISP_OFFSET = const(0xD3)
SET_COM_PIN_CFG = const(0xDA)
SET_DISP_CLK_DIV = const(0xD5)
SET_PRECHARGE = const(0xD9)
SET_VCOM_DESEL = const(0xDB)
SET_CHARGE_PUMP = const(0x8D)


class SSD1306:
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        self.framebuf = framebuf.FrameBuffer(
            self.buffer, self.width, self.height, framebuf.MONO_VLSB
        )
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP | 0x00,
            SET_MEM_ADDR,
            0x00,
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,
            SET_MUX_RATIO,
            self.height - 1,
            SET_COM_OUT_DIR | 0x08,
            SET_DISP_OFFSET,
            0x00,
            SET_COM_PIN_CFG,
            0x02 if self.width > 2 * self.height else 0x12,
            SET_DISP_CLK_DIV,
            0x80,
            SET_PRECHARGE,
            0x22 if self.external_vcc else 0xF1,
            SET_VCOM_DESEL,
            0x30,
            SET_CONTRAST,
            0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP,
            0x10 if self.external_vcc else 0x14,
            SET_DISP | 0x01,
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def fill(self, color):
        self.framebuf.fill(color)

    def pixel(self, x, y, color):
        self.framebuf.pixel(x, y, color)

    def text(self, s, x, y, color=1):
        self.framebuf.text(s, x, y, color)

    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width == 64:
            x0 += 32
            x1 += 32
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        # Chunk writes to reduce bus timeout risk on some boards/firmwares.
        step = 16
        for i in range(0, len(buf), step):
            self.i2c.writeto(self.addr, b"\x40" + buf[i : i + step])


I2C_CANDIDATES = [
    (1, 7, 6),
    (0, 1, 0),
    (0, 5, 4),
    (0, 9, 8),
    (1, 3, 2),
    (1, 11, 10),
]

OLED_WIDTH = 128
OLED_HEIGHT = 32

E1_CLK_PIN = 2
E1_DT_PIN = 3
E1_SW_PIN = 4

E2_CLK_PIN = 12
E2_DT_PIN = 13
E2_SW_PIN = 14


def try_init_display(bus, addr):
    disp = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, bus, addr=addr)
    disp.fill(1)
    disp.show()
    utime.sleep_ms(30)
    disp.fill(0)
    disp.show()
    return disp


def find_working_display():
    errors = []
    for i2c_id, scl_pin, sda_pin in I2C_CANDIDATES:
        try:
            bus = I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=100000)
            addrs = bus.scan()
        except Exception as e:
            errors.append("bus {} GP{}/GP{} init: {}".format(i2c_id, scl_pin, sda_pin, e))
            continue

        if not addrs:
            continue

        preferred = []
        if 0x3C in addrs:
            preferred.append(0x3C)
        if 0x3D in addrs:
            preferred.append(0x3D)
        for a in addrs:
            if a not in preferred:
                preferred.append(a)

        for addr in preferred:
            try:
                display = try_init_display(bus, addr)
                return display, i2c_id, scl_pin, sda_pin, addrs, addr
            except OSError as e:
                errors.append(
                    "bus {} GP{}/GP{} addr {} write: {}".format(
                        i2c_id, scl_pin, sda_pin, hex(addr), e
                    )
                )
                continue

    msg = "No working OLED found. Check VCC->3V3, GND->GND, and SCK/SDA wiring."
    if errors:
        msg += " Last errors: " + " | ".join(errors[:3])
    raise OSError(msg)


def draw_brush(px, py):
    # 3x3 cursor ring: white border with black center for visibility.
    for oy in (-1, 0, 1):
        yy = py + oy
        if yy < 0 or yy >= DRAW_H:
            continue
        for ox in (-1, 0, 1):
            xx = px + ox
            if 0 <= xx < DRAW_W:
                display.pixel(xx, yy, 1)

    if 0 <= px < DRAW_W and 0 <= py < DRAW_H:
        display.pixel(px, py, 0)


def draw_startup_test():
    display.fill(1)
    display.show()
    utime.sleep_ms(100)

    display.fill(0)
    for xx in range(DRAW_W):
        display.pixel(xx, 0, 1)
        display.pixel(xx, DRAW_H - 1, 1)
    for yy in range(DRAW_H):
        display.pixel(0, yy, 1)
        display.pixel(DRAW_W - 1, yy, 1)

    cx = DRAW_W // 2
    cy = DRAW_H // 2
    for xx in range(DRAW_W):
        display.pixel(xx, cy, 1)
    for yy in range(DRAW_H):
        display.pixel(cx, yy, 1)

    display.text("OLED OK", 4, 4, 1)
    display.show()
    utime.sleep_ms(400)


display, i2c_id, scl_pin, sda_pin, addrs, addr = find_working_display()
DRAW_W = OLED_WIDTH
DRAW_H = OLED_HEIGHT

draw_startup_test()
display.fill(0)

e1_clk = Pin(E1_CLK_PIN, Pin.IN, Pin.PULL_UP)
e1_dt = Pin(E1_DT_PIN, Pin.IN, Pin.PULL_UP)
e1_sw = Pin(E1_SW_PIN, Pin.IN, Pin.PULL_UP)

e2_clk = Pin(E2_CLK_PIN, Pin.IN, Pin.PULL_UP)
e2_dt = Pin(E2_DT_PIN, Pin.IN, Pin.PULL_UP)
e2_sw = Pin(E2_SW_PIN, Pin.IN, Pin.PULL_UP)

x = DRAW_W // 2
y = DRAW_H // 2
draw_brush(x, y)
display.show()

points = [(x, y, 0)]
redo_stack = []

draw_time_ms = 0
last_move_real_ms = None
MAX_MOVE_GAP_MS = 150

last_clk1 = e1_clk.value()
last_clk2 = e2_clk.value()
pending_dx = 0
pending_dy = 0
pending_undo = False
pending_redo = False

UNDO_HOLD_DELAY_MS = 350
REDO_HOLD_DELAY_MS = 350
HOLD_REPEAT_MS = 90
undo_hold_active = False
redo_hold_active = False
next_undo_repeat_ms = 0
next_redo_repeat_ms = 0


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def queue_move(dx, dy):
    global pending_dx, pending_dy
    pending_dx += dx
    pending_dy += dy


def rebuild_canvas_from_points():
    display.fill(0)
    for px, py, _ in points:
        draw_brush(px, py)
    display.show()


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
        draw_brush(x, y)
        display.show()
        points.append((x, y, draw_time_ms))
        redo_stack = []


def undo_last_two_seconds():
    global x, y, points
    if len(points) <= 1:
        return

    removed = points.pop()
    redo_stack.append([removed])
    x, y, _ = points[-1]
    rebuild_canvas_from_points()


def redo_last_undo():
    global x, y, points
    if not redo_stack:
        return

    restored = redo_stack.pop()
    points.extend(restored)
    x, y, _ = points[-1]
    rebuild_canvas_from_points()


print("Mini OLED drawing screen ready")
print("I2C bus:", i2c_id, "SCL=GP" + str(scl_pin), "SDA=GP" + str(sda_pin))
print("I2C addresses found:", addrs)
print("Using OLED address:", hex(addr))

while True:
    current_clk1 = e1_clk.value()
    if last_clk1 == 1 and current_clk1 == 0:
        if e1_dt.value() == 1:
            queue_move(0, 1)
        else:
            queue_move(0, -1)
    last_clk1 = current_clk1

    current_clk2 = e2_clk.value()
    if last_clk2 == 1 and current_clk2 == 0:
        if e2_dt.value() == 1:
            queue_move(1, 0)
        else:
            queue_move(-1, 0)
    last_clk2 = current_clk2

    now = utime.ticks_ms()

    current_sw1 = e1_sw.value()
    if current_sw1 == 0:
        if not undo_hold_active:
            pending_undo = True
            undo_hold_active = True
            next_undo_repeat_ms = utime.ticks_add(now, UNDO_HOLD_DELAY_MS)
        elif utime.ticks_diff(now, next_undo_repeat_ms) >= 0:
            pending_undo = True
            next_undo_repeat_ms = utime.ticks_add(now, HOLD_REPEAT_MS)
    else:
        undo_hold_active = False

    current_sw2 = e2_sw.value()
    if current_sw2 == 0:
        if not redo_hold_active:
            pending_redo = True
            redo_hold_active = True
            next_redo_repeat_ms = utime.ticks_add(now, REDO_HOLD_DELAY_MS)
        elif utime.ticks_diff(now, next_redo_repeat_ms) >= 0:
            pending_redo = True
            next_redo_repeat_ms = utime.ticks_add(now, HOLD_REPEAT_MS)
    else:
        redo_hold_active = False

    if pending_undo:
        pending_undo = False
        undo_last_two_seconds()

    if pending_redo:
        pending_redo = False
        redo_last_undo()

    moved = False
    while pending_dx != 0:
        moved = True
        if pending_dx > 0:
            pending_dx -= 1
            step_cursor(1, 0)
        else:
            pending_dx += 1
            step_cursor(-1, 0)

    while pending_dy != 0:
        moved = True
        if pending_dy > 0:
            pending_dy -= 1
            step_cursor(0, 1)
        else:
            pending_dy += 1
            step_cursor(0, -1)

    if not moved:
        utime.sleep_ms(1)






