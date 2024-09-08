import time
import sys
from pubsub import pub
import json
from meshtastic.serial_interface import SerialInterface
from meshtastic import portnums_pb2

import paho.mqtt.client as mqtt

# MQTT configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "dude"
MQTT_USERNAME = ""  # Optional
MQTT_PASSWORD = ""  # Optional


serial_port = '/dev/ttyACM0'  # Replace with your Meshtastic device's serial port

def get_user(array_of_objects, key, value):
    for obj in array_of_objects:
        if obj.get(key) == value:
            return obj
    return False

def get_node_info(serial_port):
    print("Initializing SerialInterface to get node info...")
    local = SerialInterface(serial_port)
    node_info = local.nodes
    local.close()
    print("Node info retrieved.")
    return node_info

def parse_node_info(node_info):
    print("Parsing node info...")
    nodes = []
    for node_id, node in node_info.items():
        nodes.append({
            'num': node_id,
            'user': {
                'shortName': node.get('user', {}).get('shortName', 'Unknown'),
                'longName': node.get('user', {}).get('longName', 'Unknown'),
                'macaddr': node.get('user', {}).get('macaddr', 'Unknown'),
                'hwModel': node.get('user', {}).get('hwModel', 'Unknown'),
                'lastHeard': node.get('user', {}).get('lastHeard', 'Unknown'),
                'position': node.get('position', {}),
                'deviceMetrics': node.get('deviceMetrics', {})
            }
        })
    print("Node info parsed.")
    return nodes

def on_receive(packet, interface, node_list):
    try:
        if packet['decoded']['portnum'] == 'TEXT_MESSAGE_APP':
            message = packet['decoded']['payload'].decode('utf-8')
            fromnum = packet['fromId']
            shortname = next((node['user']['shortName'] for node in node_list if node['num'] == fromnum), 'Unknown')
            print(f"RX: {shortname} - {message}")
            
            senderInfo = get_user(node_list, "num", fromnum)

            # Publish the output to the MQTT broker
            data = {
                "type": "meshtadon",
                "version": 1,
                "sender": shortname,
                "senderId": fromnum,
                "to": packet['toId'],
                "rx_time": packet['rxTime'],
                "rx_snr": packet['rxSnr'],
                "hop_limit": packet['hopLimit'],
                "rx_rssi": packet['rxRssi'],
                "hop_start": packet['hopStart'],
                "message": message,
                "senderInfo": senderInfo
            }
            publish_to_mqtt(json.dumps(data))

            print(f"Sending to MQTT topic -- {MQTT_TOPIC}: {data}")

    except KeyError:
        pass  # Ignore KeyError silently
    except UnicodeDecodeError:
        pass  # Ignore UnicodeDecodeError silently

# Function to publish the result to an MQTT broker
def publish_to_mqtt(message):
    client = mqtt.Client()
    
    # Set username and password if needed
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    # Connect to MQTT broker
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    
    # Publish the message to the topic
    client.publish(MQTT_TOPIC, message)
    
    # Disconnect from the broker
    client.disconnect()

def main():
    print(f"Using serial port: {serial_port}")

    # Retrieve and parse node information
    node_info = get_node_info(serial_port)
    node_list = parse_node_info(node_info)

    # Print node list for debugging
    print("Node List:")
    for node in node_list:
        print(node)

    # Subscribe the callback function to message reception
    def on_receive_wrapper(packet, interface):
        on_receive(packet, interface, node_list)

    pub.subscribe(on_receive_wrapper, "meshtastic.receive")
    print("Subscribed to meshtastic.receive")

    # Set up the SerialInterface for message listening
    local = SerialInterface(serial_port)
    print("SerialInterface setup for listening.")

    # Keep the script running to listen for messages
    try:
        while True:
            sys.stdout.flush()
            time.sleep(1)  # Sleep to reduce CPU usage
    except KeyboardInterrupt:
        print("Script terminated by user")
        local.close()

if __name__ == "__main__":
    main()
