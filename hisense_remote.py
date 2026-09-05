import ssl
import socket
import struct
import time
import sys

def build_handshake(mac_str):
    mac = mac_str.encode('utf-8')
    buf = bytearray()
    buf.append(1)
    buf.append(0)
    buf.extend(struct.pack('>H', 0))
    buf.extend(struct.pack('>I', 1))
    buf.extend(struct.pack('>I', 1))
    buf.append(0x20)
    buf.append(3)
    buf.append(0)
    buf.append(0)
    buf.append(0)
    buf.extend(struct.pack('>I', len(mac)))
    buf.extend(mac)
    buf[2:4] = struct.pack('>H', len(buf) - 4)
    return buf

def build_key_command(action, key_code):
    b = bytearray()
    b.append(1)
    b.append(2)
    b.extend(struct.pack('>H', 0))
    b.extend(struct.pack('>q', int(time.time()))) # sequence number
    b.extend(struct.pack('>I', action))
    b.extend(struct.pack('>I', key_code))
    b[2:4] = struct.pack('>H', len(b) - 4)
    return b

def send_key(key_code, ip='192.168.1.4'):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers('DEFAULT@SECLEVEL=0')
    ctx.load_cert_chain(certfile='cert1024.pem', keyfile='key1024.pem')
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    
    try:
        ssl_sock = ctx.wrap_socket(s)
        ssl_sock.connect((ip, 6466))
        print(f"Connected to {ip}:6466")
        
        # Read spontaneous greeting
        greeting = ssl_sock.recv(1024)
        print("Greeting:", greeting.hex())
        
        # Send handshake
        handshake = build_handshake("aa:bb:cc:dd:ee:ff")
        ssl_sock.send(handshake)
        
        # Read handshake response
        resp = ssl_sock.recv(1024)
        print("Handshake Response:", resp.hex())
        
        # Send Key DOWN
        print(f"Sending KEYCODE {key_code} DOWN...")
        ssl_sock.send(build_key_command(0, key_code))
        time.sleep(0.1)
        
        # Send Key UP
        print(f"Sending KEYCODE {key_code} UP...")
        ssl_sock.send(build_key_command(2, key_code))
        
        print("Command sent successfully!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Send commands to Android TV')
    parser.add_argument('key', type=str, help='The key to send, e.g., VOLUME_UP, HOME, 25')
    parser.add_argument('--ip', type=str, default='192.168.1.4', help='TV IP address')
    args = parser.parse_args()
    
    # ICONE / Standard Android Keycodes
    keys_dict = {
        # Power & Input
        "POWER": 26, "STB": 26, "TV": 177, "SOURCE": 178,
        
        # Numbers
        "0": 7, "1": 8, "2": 9, "3": 10, "4": 11,
        "5": 12, "6": 13, "7": 14, "8": 15, "9": 16,
        "IP/SAT": 237, "VOD": 172,
        
        # Navigation
        "INFO": 165, "RECALL": 229, "MENU": 82, "EXIT": 4, "BACK": 4,
        "UP": 19, "DOWN": 20, "LEFT": 21, "RIGHT": 22, "OK": 23, "ENTER": 66,
        
        # Middle buttons
        "FAVORITE": 274, "EPG": 172, "PLAYLIST": 226,
        "VOL+": 24, "VOLUME_UP": 24, "VOL-": 25, "VOLUME_DOWN": 25,
        "MUTE": 164, "CH+": 166, "CH-": 167,
        
        # Colored buttons
        "RED": 183, "GREEN": 184, "YELLOW": 185, "BLUE": 186,
        
        # Bottom block
        "TELETEXT": 233, "SLEEP": 223, "SUBTITLE": 175, "RADIO/TV": 232,
        "PIP": 171, "RESOLUTION": 230, "CURSOR": 110, "V.FORMAT": 258,
        
        # Media Controls
        "PLAY_PAUSE": 85, "STOP": 86, "RECORD": 130,
        "REWIND": 89, "FAST_FORWARD": 90, 
        "PREVIOUS": 88, "NEXT": 87
    }
    
    # Prioritize checking the dictionary for aliases (including "0"-"9")
    if args.key.upper() in keys_dict:
        key = keys_dict[args.key.upper()]
    else:
        try:
            # If not in dictionary, try parsing as raw Android KeyEvent integer
            key = int(args.key)
        except ValueError:
            print(f"Unknown key alias: {args.key}. Using fallback 25 (VOL-)")
            key = 25
    
    send_key(key, ip=args.ip)
