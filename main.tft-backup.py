from machine import Pin, SPI
import utime

# 240x320 TFT (ILI9341) on SPI0
# SCK=GP18, MOSI=GP19, MISO=GP16, D/C=GP20, CS=GP17
ILI9341_SWRESET = 0x01
ILI9341_SLPOUT = 0x11
ILI9341_DISPON = 0x29
ILI9341_CASET = 0x2A
ILI9341_PASET = 0x2B
ILI9341_RAMWR = 0x2C


class ILI9341:
    def __init__(self, width, height, spi, dc, cs, rst=None):
        self.width = width
        self.height = height
        self.spi = spi
        self.dc = dc
        self.cs = cs
        self.rst = rst

        self.dc.init(self.dc.OUT, value=0)
        self.cs.init(self.cs.OUT, value=1)
        if self.rst is not None:
            self.rst.init(self.rst.OUT, value=1)

        self._init_display()

    def _write_cmd(self, cmd):
        self.cs(0)
        self.dc(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def _write_data(self, data):
        self.cs(0)
        self.dc(1)
        self.spi.write(data)
        self.cs(1)

    def _write_cmd_data(self, cmd, data):
        self._write_cmd(cmd)
        if data:
            self._write_data(data)

    def _hard_reset(self):
        if self.rst is None:
            return
        self.rst(1)
        utime.sleep_ms(5)
        self.rst(0)
        utime.sleep_ms(20)
        self.rst(1)
        utime.sleep_ms(120)

    def _set_window(self, x0, y0, x1, y1):
        self._write_cmd(ILI9341_CASET)
        self._write_data(bytearray([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self._write_cmd(ILI9341_PASET)
        self._write_data(bytearray([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self._write_cmd(ILI9341_RAMWR)

    def _init_display(self):
        self._hard_reset()
        self._write_cmd(ILI9341_SWRESET)
        utime.sleep_ms(120)

        self._write_cmd_data(0xEF, b"\x03\x80\x02")
        self._write_cmd_data(0xCF, b"\x00\xC1\x30")
        self._write_cmd_data(0xED, b"\x64\x03\x12\x81")
        self._write_cmd_data(0xE8, b"\x85\x00\x78")
        self._write_cmd_data(0xCB, b"\x39\x2C\x00\x34\x02")
        self._write_cmd_data(0xF7, b"\x20")
        self._write_cmd_data(0xEA, b"\x00\x00")
        self._write_cmd_data(0xC0, b"\x23")
        self._write_cmd_data(0xC1, b"\x10")
        self._write_cmd_data(0xC5, b"\x3E\x28")
        self._write_cmd_data(0xC7, b"\x86")
        self._write_cmd_data(0x36, b"\x48")
        self._write_cmd_data(0x3A, b"\x55")
        self._write_cmd_data(0xB1, b"\x00\x18")
        self._write_cmd_data(0xB6, b"\x08\x82\x27")
        self._write_cmd_data(0xF2, b"\x00")
        self._write_cmd_data(0x26, b"\x01")
        self._write_cmd_data(
            0xE0,
            b"\x0F\x31\x2B\x0C\x0E\x08\x4E\xF1\x37\x07\x10\x03\x0E\x09\x00",
        )
        self._write_cmd_data(
            0xE1,
            b"\x00\x0E\x14\x03\x11\x07\x31\xC1\x48\x08\x0F\x0C\x31\x36\x0F",
        )
        self._write_cmd(ILI9341_SLPOUT)
        utime.sleep_ms(120)
        self._write_cmd(ILI9341_DISPON)
        utime.sleep_ms(20)

    def pixel(self, x, y, color):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        self._set_window(x, y, x, y)
        self._write_data(bytearray([color >> 8, color & 0xFF]))

    def fill(self, color):
        self._set_window(0, 0, self.width - 1, self.height - 1)
        row = bytearray(self.width * 2)
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        for i in range(0, len(row), 2):
            row[i] = hi
            row[i + 1] = lo
        for _ in range(self.height):
            self._write_data(row)

    def show(self):
        # Immediate mode driver writes directly.
        pass


spi = SPI(
    0,
    baudrate=10_000_000,
    polarity=0,
    phase=0,
    sck=Pin(18),
    mosi=Pin(19),
    miso=Pin(16),
)
display = ILI9341(
    240,
    320,
    spi,
    dc=Pin(20, Pin.OUT),
    cs=Pin(17, Pin.OUT),
    rst=None,
)

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

WHITE = 0xFFFF
BLACK = 0x0000

DRAW_W = 240
DRAW_H = 320

display.fill(0xF800)
utime.sleep_ms(200)
display.fill(BLACK)

x = DRAW_W // 2
y = DRAW_H // 2
display.pixel(x, y, WHITE)

points = [(x, y, 0)]
redo_stack = []

draw_time_ms = 0
last_move_real_ms = None
MAX_MOVE_GAP_MS = 150

last_clk1 = e1_clk.value()
last_clk2 = e2_clk.value()
last_sw1 = e1_sw.value()
last_sw2 = e2_sw.value()
last_btn1_ms = 0
last_btn2_ms = 0

dirty = False
pending_dx = 0
pending_dy = 0
pending_undo = False
pending_redo = False


def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def mark_dirty():
    global dirty
    dirty = True


def queue_move(dx, dy):
    global pending_dx, pending_dy
    pending_dx += dx
    pending_dy += dy


def rebuild_canvas_from_points():
    display.fill(BLACK)
    for px, py, _ in points:
        display.pixel(px, py, WHITE)


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
        display.pixel(x, y, WHITE)
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


print("Wokwi TFT drawing screen ready")

while True:
    current_clk1 = e1_clk.value()
    if last_clk1 == 1 and current_clk1 == 0:
        if e1_dt.value() == 1:
            queue_move(0, -1)
        else:
            queue_move(0, 1)
    last_clk1 = current_clk1

    current_clk2 = e2_clk.value()
    if last_clk2 == 1 and current_clk2 == 0:
        if e2_dt.value() == 1:
            queue_move(1, 0)
        else:
            queue_move(-1, 0)
    last_clk2 = current_clk2

    current_sw1 = e1_sw.value()
    now = utime.ticks_ms()
    if last_sw1 == 1 and current_sw1 == 0 and utime.ticks_diff(now, last_btn1_ms) > 200:
        pending_undo = True
        last_btn1_ms = now
    last_sw1 = current_sw1

    current_sw2 = e2_sw.value()
    if last_sw2 == 1 and current_sw2 == 0 and utime.ticks_diff(now, last_btn2_ms) > 200:
        pending_redo = True
        last_btn2_ms = now
    last_sw2 = current_sw2

    if pending_undo:
        pending_undo = False
        undo_last_two_seconds(utime.ticks_ms())

    if pending_redo:
        pending_redo = False
        redo_last_undo()

    while pending_dx != 0:
        if pending_dx > 0:
            pending_dx -= 1
            step_cursor(1, 0)
        else:
            pending_dx += 1
            step_cursor(-1, 0)

    while pending_dy != 0:
        if pending_dy > 0:
            pending_dy -= 1
            step_cursor(0, 1)
        else:
            pending_dy += 1
            step_cursor(0, -1)

    utime.sleep_ms(1)
