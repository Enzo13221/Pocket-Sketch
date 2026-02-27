from machine import Pin, I2C
import utime

# 1602 I2C backpack (PCF8574) pin map
LCD_RS = 0x01
LCD_RW = 0x02
LCD_E = 0x04
LCD_BACKLIGHT = 0x08

LCD_CMD_CLEAR = 0x01
LCD_CMD_HOME = 0x02
LCD_CMD_ENTRY_MODE = 0x04
LCD_CMD_DISPLAY_CTRL = 0x08
LCD_CMD_FUNCTION = 0x20
LCD_CMD_SET_DDRAM = 0x80


class LCD1602_I2C:
    def __init__(self, i2c, addr, cols=16, rows=2):
        self.i2c = i2c
        self.addr = addr
        self.cols = cols
        self.rows = rows
        self.backlight = LCD_BACKLIGHT
        self._init_lcd()

    def _write_byte(self, data):
        self.i2c.writeto(self.addr, bytes([data]))

    def _pulse_enable(self, data):
        self._write_byte(data | LCD_E)
        utime.sleep_us(1)
        self._write_byte(data & ~LCD_E)
        utime.sleep_us(50)

    def _write4(self, value, mode=0):
        data = ((value & 0x0F) << 4) | self.backlight
        if mode:
            data |= LCD_RS
        self._write_byte(data)
        self._pulse_enable(data)

    def _send(self, value, mode=0):
        self._write4(value >> 4, mode)
        self._write4(value & 0x0F, mode)

    def command(self, cmd):
        self._send(cmd, 0)
        if cmd == LCD_CMD_CLEAR or cmd == LCD_CMD_HOME:
            utime.sleep_ms(2)

    def putchar(self, ch):
        self._send(ord(ch), 1)

    def putstr(self, s):
        for ch in s:
            self.putchar(ch)

    def move_to(self, col, row):
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        self.command(LCD_CMD_SET_DDRAM | (col + row_offsets[row]))

    def clear(self):
        self.command(LCD_CMD_CLEAR)

    def write_row(self, row, text):
        self.move_to(0, row)
        s = str(text)
        if len(s) < self.cols:
            s = s + (" " * (self.cols - len(s)))
        self.putstr(s[: self.cols])

    def _init_lcd(self):
        utime.sleep_ms(50)
        self._write4(0x03)
        utime.sleep_ms(5)
        self._write4(0x03)
        utime.sleep_us(150)
        self._write4(0x03)
        self._write4(0x02)

        self.command(LCD_CMD_FUNCTION | 0x08)   # 4-bit, 2-line, 5x8 dots
        self.command(LCD_CMD_DISPLAY_CTRL | 0x0F)  # display on, cursor on, blink on
        self.command(LCD_CMD_CLEAR)
        self.command(LCD_CMD_ENTRY_MODE | 0x02)  # increment


I2C_CANDIDATES = [
    (1, 7, 6),
    (0, 1, 0),
    (0, 5, 4),
    (0, 9, 8),
    (1, 3, 2),
    (1, 11, 10),
]

LCD_COLS = 16
LCD_ROWS = 2

# Encoder 1 controls X (direction already swapped to your preference)
E1_CLK_PIN = 2
E1_DT_PIN = 3
E1_SW_PIN = 4

# Encoder 2 controls Y
E2_CLK_PIN = 12
E2_DT_PIN = 13
E2_SW_PIN = 14


def find_working_lcd():
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
        if 0x27 in addrs:
            preferred.append(0x27)
        if 0x3F in addrs:
            preferred.append(0x3F)
        for a in addrs:
            if a not in preferred:
                preferred.append(a)

        for addr in preferred:
            try:
                lcd = LCD1602_I2C(bus, addr, LCD_COLS, LCD_ROWS)
                lcd.write_row(0, "LCD1602 READY")
                lcd.write_row(1, "Addr {}".format(hex(addr)))
                utime.sleep_ms(500)
                lcd.clear()
                return lcd, i2c_id, scl_pin, sda_pin, addrs, addr
            except OSError as e:
                errors.append(
                    "bus {} GP{}/GP{} addr {} write: {}".format(
                        i2c_id, scl_pin, sda_pin, hex(addr), e
                    )
                )
                continue

    msg = "No working 1602 I2C LCD found. Check VCC->5V/3V3, GND, SCK->SCL, SDA."
    if errors:
        msg += " Last errors: " + " | ".join(errors[:3])
    raise OSError(msg)


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
    global canvas
    canvas = [[" " for _ in range(DRAW_W)] for _ in range(DRAW_H)]
    for px, py in points:
        canvas[py][px] = "#"
    render()


def render():
    row0 = canvas[0][:]
    row1 = canvas[1][:]

    if y == 0:
        row0[x] = "@"
    else:
        row1[x] = "@"

    lcd.write_row(0, "".join(row0))
    lcd.write_row(1, "".join(row1))


def step_cursor(dx, dy):
    global x, y, redo_stack

    nx = clamp(x + dx, 0, DRAW_W - 1)
    ny = clamp(y + dy, 0, DRAW_H - 1)
    if nx != x or ny != y:
        x = nx
        y = ny
        canvas[y][x] = "#"
        points.append((x, y))
        redo_stack = []
        render()


def undo_step():
    global x, y, points
    if len(points) <= 1:
        return

    removed = points.pop()
    redo_stack.append([removed])
    x, y = points[-1]
    rebuild_canvas_from_points()


def redo_step():
    global x, y, points
    if not redo_stack:
        return

    restored = redo_stack.pop()
    points.extend(restored)
    x, y = points[-1]
    rebuild_canvas_from_points()


lcd, i2c_id, scl_pin, sda_pin, addrs, addr = find_working_lcd()

DRAW_W = LCD_COLS
DRAW_H = LCD_ROWS

canvas = [[" " for _ in range(DRAW_W)] for _ in range(DRAW_H)]

# Strong visual check on boot.
lcd.write_row(0, "SKETCH READY")
lcd.write_row(1, "X=-- Y=-")
lcd.move_to(0, 0)
utime.sleep_ms(400)

x = DRAW_W // 2
y = DRAW_H // 2
canvas[y][x] = "#"
points = [(x, y)]
redo_stack = []

render()

e1_clk = Pin(E1_CLK_PIN, Pin.IN, Pin.PULL_UP)
e1_dt = Pin(E1_DT_PIN, Pin.IN, Pin.PULL_UP)
e1_sw = Pin(E1_SW_PIN, Pin.IN, Pin.PULL_UP)

e2_clk = Pin(E2_CLK_PIN, Pin.IN, Pin.PULL_UP)
e2_dt = Pin(E2_DT_PIN, Pin.IN, Pin.PULL_UP)
e2_sw = Pin(E2_SW_PIN, Pin.IN, Pin.PULL_UP)

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

print("LCD1602 sketch ready")
print("I2C bus:", i2c_id, "SCL=GP" + str(scl_pin), "SDA=GP" + str(sda_pin))
print("I2C addresses found:", addrs)
print("Using LCD address:", hex(addr))

while True:
    current_clk1 = e1_clk.value()
    if last_clk1 == 1 and current_clk1 == 0:
        # Swapped direction for encoder 1.
        if e1_dt.value() == 1:
            queue_move(1, 0)
        else:
            queue_move(-1, 0)
    last_clk1 = current_clk1

    current_clk2 = e2_clk.value()
    if last_clk2 == 1 and current_clk2 == 0:
        if e2_dt.value() == 1:
            queue_move(0, 1)
        else:
            queue_move(0, -1)
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
        undo_step()

    if pending_redo:
        pending_redo = False
        redo_step()

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

