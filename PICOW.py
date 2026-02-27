from machine import Pin, ADC 
import time 

# 5-pin joystick pins
X_AXIS = ADC(Pin(26))  # GPIO 26 (ADC0) - left/right
Y_AXIS = ADC(Pin(27))  # GPIO 27 (ADC1) - up/down
SW = Pin(22, Pin.IN, Pin.PULL_UP)  # GPIO 22 - button (active low)

def read_joystick():
    # Read analog values (0-65535)
    x = X_AXIS.read_u16()
    y = Y_AXIS.read_u16()
    
    # Scale to -100 to +100 for easier reading
    x_scaled = (x // 655) - 100  # 655 = 65535 / 100
    y_scaled = (y // 655) - 100
    
    # Detect movement (ignore small drifts near center)
    if abs(x_scaled) > 10 or abs(y_scaled) > 10:
        print(f"X: {x_scaled:4d}  Y: {y_scaled:4d}")

def check_button():
    if SW.value() == 0:  # Button pressed (active low)
        print("Button pressed!")
        time.sleep(0.2)  # debounce

print("5-Pin Joystick Reader Started")
print("Move the joystick and press the button...")

# Main loop
while True:
    read_joystick()
    check_button()
    time.sleep(0.01)  # 100ms update interval