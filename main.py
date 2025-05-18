import network
import time
from machine import Pin, PWM
from umqtt.simple import MQTTClient
import secrets  # Import credentials from separate file
import ujson
import plasma
from pimoroni import RGBLED

NUM_LEDS = 144

# Topics
MQTT_TOPIC_SUB = b'PLASMA'
MQTT_TOPIC_ALIVE = b'PLASMA/ALIVE'

#Onboard RGB LED:
led = RGBLED()
led.set_rgb(25, 0, 0)

#Initialise strip to pinky:
led_strip = plasma.WS2812(NUM_LEDS, rgbw=True, color_order=plasma.COLOR_ORDER_GRB)
led_strip.start()

#Test strip:
#for i in range(NUM_LEDS):
#    led_strip.set_rgb(i, 30, 0, 30,30) 

# Connect to Wi-Fi using credentials from secrets.py
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(1)
    print("Wi-Fi connected:", wlan.ifconfig())
    led.set_rgb(0, 25, 40)

def mqtt_callback(topic, msg):
    print(f"MQTT received on {topic}: {msg}")
    try:
        data = ujson.loads(msg)
        raw_colours = data.get("colours", "")
        raw_splits = data.get("splits", "")
        colour_list = ['#' + c for c in raw_colours.split('#') if c]
        split_indices = [int(c) for c in raw_splits if c.isdigit()]
        split_len = len(split_indices)
        if split_len == 0 or not colour_list:
            print("Invalid or empty splits/colours.")
            led.set_rgb(50, 0, 0)
            return
        leds_per_section = NUM_LEDS // split_len
        remainder = NUM_LEDS % split_len
        led_index = 0
        for i, idx in enumerate(split_indices):
            if idx >= len(colour_list):
                print(f"Index {idx} out of range.")
                led.set_rgb(50, 0, 0)
                continue
            hex_col = colour_list[idx]
            try:
                r = int(hex_col[1:3], 16)
                g = int(hex_col[3:5], 16)
                b = int(hex_col[5:7], 16)
                w = int(hex_col[7:9], 16) if len(hex_col) == 9 else 0
            except ValueError:
                print(f"Invalid colour value: {hex_col}")
                led.set_rgb(50, 0, 0)
                continue
            count = leds_per_section + (1 if i < remainder else 0)
            for _ in range(count):
                if led_index < NUM_LEDS:
                    led_strip.set_rgb(led_index, r, g, b, w)
                    led_index += 1
        # Optional: blank unused LEDs
        for i in range(led_index, NUM_LEDS):
            led_strip.set_rgb(i, 0, 0, 0, 0)
        print(f"LEDs updated: {led_index} pixels written.")
        led.set_rgb(0, 25, 0)
    except Exception as e:
        led.set_rgb(50, 0, 0)
        print("Error processing message:", e)


# Connect to MQTT broker
def connect_mqtt():
    global client
    client = MQTTClient(secrets.MQTT_CLIENT_ID, secrets.MQTT_BROKER)
    client.set_callback(mqtt_callback)
    client.connect()
    print("Connected to MQTT broker.")
    client.subscribe(MQTT_TOPIC_SUB)
    print(f"Subscribed to topic: {MQTT_TOPIC_SUB.decode()}")
    led.set_rgb(0, 25, 0)

# Main loop: keep connection alive and publish heartbeat
def main():
    connect_wifi()
    connect_mqtt()
    last_alive = time.ticks_ms()
    alive_interval = 2000  # ms
    try:
        while True:
            client.check_msg()  # Non-blocking check for new messages
            now = time.ticks_ms()
            # Publish alive message every interval
            if time.ticks_diff(now, last_alive) >= alive_interval:
                client.publish(MQTT_TOPIC_ALIVE, b'ALIVE')
                print("Published heartbeat to PLASMA/ALIVE")
                last_alive = now
            time.sleep(0.05)

    except Exception as e:
        print("Error:", e)
        client.disconnect()

# Entrypoint
if __name__ == '__main__':
    main()
