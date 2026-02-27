from micropython import const
import framebuf
import time


ST7789_SWRESET = const(0x01)
ST7789_SLPOUT = const(0x11)
ST7789_COLMOD = const(0x3A)
ST7789_MADCTL = const(0x36)
ST7789_CASET = const(0x2A)
ST7789_RASET = const(0x2B)
ST7789_RAMWR = const(0x2C)
ST7789_INVON = const(0x21)
ST7789_NORON = const(0x13)
ST7789_DISPON = const(0x29)


class ST7789(framebuf.FrameBuffer):
    def __init__(
        self,
        width,
        height,
        spi,
        dc,
        reset,
        cs=None,
        bl=None,
        xstart=0,
        ystart=0,
    ):
        self.width = width
        self.height = height
        self.spi = spi
        self.dc = dc
        self.reset = reset
        self.cs = cs
        self.bl = bl
        self.xstart = xstart
        self.ystart = ystart

        self.dc.init(self.dc.OUT, value=0)
        self.reset.init(self.reset.OUT, value=1)
        if self.cs is not None:
            self.cs.init(self.cs.OUT, value=1)
        if self.bl is not None:
            self.bl.init(self.bl.OUT, value=1)

        self.buffer = bytearray(self.width * self.height * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)

        self._init_display()
        self.fill(0x0000)
        self.show()

    def _write_cmd(self, cmd):
        if self.cs is not None:
            self.cs(0)
        self.dc(0)
        self.spi.write(bytearray([cmd]))
        if self.cs is not None:
            self.cs(1)

    def _write_data(self, data):
        if self.cs is not None:
            self.cs(0)
        self.dc(1)
        self.spi.write(data)
        if self.cs is not None:
            self.cs(1)

    def _hard_reset(self):
        self.reset(1)
        time.sleep_ms(50)
        self.reset(0)
        time.sleep_ms(50)
        self.reset(1)
        time.sleep_ms(120)

    def _set_window(self, x0, y0, x1, y1):
        x0 += self.xstart
        x1 += self.xstart
        y0 += self.ystart
        y1 += self.ystart

        self._write_cmd(ST7789_CASET)
        self._write_data(bytearray([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))

        self._write_cmd(ST7789_RASET)
        self._write_data(bytearray([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))

        self._write_cmd(ST7789_RAMWR)

    def _init_display(self):
        self._hard_reset()
        self._write_cmd(ST7789_SWRESET)
        time.sleep_ms(150)
        self._write_cmd(ST7789_SLPOUT)
        time.sleep_ms(120)

        self._write_cmd(ST7789_COLMOD)
        self._write_data(b"\x55")  # 16-bit color

        self._write_cmd(ST7789_MADCTL)
        self._write_data(b"\x00")

        self._write_cmd(ST7789_INVON)
        self._write_cmd(ST7789_NORON)
        time.sleep_ms(10)
        self._write_cmd(ST7789_DISPON)
        time.sleep_ms(120)

    def show(self):
        self._set_window(0, 0, self.width - 1, self.height - 1)
        self._write_data(self.buffer)
