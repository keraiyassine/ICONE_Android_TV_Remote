# ICONE IRON PRO / HiSilicon Android TV - Reverse Engineering the Remote Protocol

This repository contains a fully functional, standalone Python implementation for pairing and controlling custom Android TV boxes—specifically the **ICONE IRON PRO** (and likely other devices based on the **HiSilicon Hi3798MV200** chipset).

This project is the result of an extensive reverse-engineering effort. What started as a simple attempt to use standard Google Android TV protocols turned into a deep-dive into decompiled Smali bytecode, legacy SSL workarounds, and a proprietary, undocumented binary protocol.

Here is the complete chronicle of how we built this from the ground up, the roadblocks we hit, and exactly how we bypassed them.

---

## The Reverse Engineering Journey

### Phase 0: The Illusion of Standard Android TV

**The Initial Plan:**
We initially attempted to use off-the-shelf Python libraries like `androidtvremote2` and `atvremote` to control the TV. Since the TV runs Android 7.0 and advertises an Android TV Remote Service on ports 6466/6467, we assumed it would follow standard Google protocols. We wrote a quick test script (`pair_test.py`) using `androidtvremote2` to initiate the pairing process.

**The Roadblock:**
The standard libraries completely failed to connect. `androidtvremote2` threw fatal SSL handshake errors (`CERTIFICATE_VERIFY_FAILED`). The library enforces strict, modern OpenSSL security policies, which immediately rejected the TV's connection. 

This total failure of standard tools proved that the TV was doing something highly non-standard, forcing us to abandon out-of-the-box solutions and begin reverse-engineering the protocol from scratch.

---

### Phase 1: The SSL Certificate Blockade (Port 6467 Pairing)

**The Initial Plan:** 
Android TVs normally use the Google Polo Pairing Protocol over port `6467`. The plan was to connect to this port using a standard Python SSL socket, initiate a pairing request, input the 4-digit hex code shown on the TV, and generate the required cryptographic Alpha hash.

**The Roadblock:**
Whenever the Python script attempted to connect, it instantly threw an `ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]` or handshake failure. Python completely refused to negotiate the TLS connection. 

**The Investigation & Solution:**
We analyzed the TLS handshake and dumped the TV's certificate. We discovered that the TV's firmware was using a legacy **1024-bit RSA key**. Modern OpenSSL libraries (used in Python 3.10+) strictly enforce a minimum of 2048-bit security and will instantly sever connections to anything lower. 

To trick the socket into connecting, we had to:
1. Generate our own 1024-bit RSA certificate and key using OpenSSL to match the TV's expectation.
2. Explicitly downgrade Python's SSL security restrictions using `ctx.set_ciphers('DEFAULT@SECLEVEL=0')`.

With the security downgraded, the TLS connection succeeded. We successfully received the pairing payloads, computed the Base64 Alpha hash of the hex code, and sent it back. **Pairing was successful.** *(Implemented in `hisense_pair.py`)*.

---

### Phase 2: The Silent Treatment (Port 6466 Control)

**The Initial Plan:**
With pairing complete, the next step was sending keystrokes. Standard Android TVs listen on port `6466` for Google `remotemessage.proto` Protocol Buffer (Protobuf) messages. We built a script to send a `RemoteConfigure` intent, a `RemoteSetActive` intent, and finally a `RemoteKeyInject` intent (e.g., `KEYCODE_VOLUME_DOWN`).

**The Roadblock:**
The TV accepted the TLS connection on port 6466 perfectly. However, it completely ignored every Protobuf message we sent. The volume didn't change, the d-pad didn't move. Instead, the TV responded with a mysterious raw hex sequence: `01 14 00 00`. 

We realized this TV was **not** using the standard Google Android TV protocol, despite running Android.

---

### Phase 3: Decompiling the Unimote APK

To figure out how the TV was meant to be controlled, we extracted and decompiled the official **Unimote** Android APK using `apktool`. 

**The Investigation:**
Digging through thousands of obfuscated Smali files, we tracked the network connection logic. We found that Unimote *does* contain the standard `com.google.polo.wire.protobuf` libraries, but for our specific IP, it was branching into a different execution path. 

We traced the execution to a network handler in `t8/i.smali` and a byte-packet builder in `u8/a.smali`. We analyzed the raw byte arrays being constructed and pushed to the `OutputStream`. 

**The Breakthrough:**
We discovered that the TV (which identified itself in network logs as `HiSTBAndroidV6/Hi3798MV200` running Android 7.0 `NRD90M`) utilizes a **completely proprietary, undocumented custom binary protocol**. 

---

### Phase 4: Decoding the Proprietary HiSilicon Protocol

By reverse-engineering the `u8/a.smali` class, we decoded exactly how to talk to this specific chipset:

**1. The Mandatory Handshake:**
The reason the TV was ignoring our Protobufs and sending back `01 14 00 00` was because it was waiting for a highly specific initialization packet. We discovered a method (`a(String)`) that builds a 22-byte payload starting with `01 00` and ending with a MAC address string.
*We replicated this in Python: If you send this 22-byte dummy MAC address immediately upon connecting, the TV replies with a massive binary payload detailing its model (`ICONE IRON PRO`) and unlocks the control interface.*

**2. The Key Injection Packet:**
Instead of a complex Protobuf, keystrokes are sent via a raw 20-byte packet generated by a method we found called `b(II)[B]`. We mapped its structure:
*   Byte 0: `01`
*   Byte 1: `02`
*   Bytes 2-3: Payload Length
*   Bytes 4-11: Timestamp/Sequence Number
*   Bytes 12-15: Action (`0` for `ACTION_DOWN`, `2` for `ACTION_UP`)
*   Bytes 16-19: Standard Android `KeyEvent` integer (e.g., `25` for Vol Down).

We completely gutted our `hisense_remote.py` script, discarded the Google Protobufs, and wrote a custom byte-array builder matching this exact specification. **It worked instantly. The TV responded to the keystrokes.**

---

### Phase 5: The Missing Hardware Keys

**The Problem:**
While mapping out the physical remote control to the Python script, we found that all standard keys (D-Pad, Volume, Power, Numbers, Media controls) worked perfectly. However, specialized hardware keys like `INFO` and `FAVORITE` did not trigger the TV's UI.

**The Investigation:**
To ensure we weren't just guessing the wrong Android KeyEvents, we wrote a brute-force loop. We systematically injected every single Android keycode from `1` to `350` into the TV's network driver and observed the screen.

**The Conclusion:**
The firmware engineers who built the ICONE / HiSilicon Android ROM deliberately omitted network-layer intent mappings for their custom UI overlays (like the Info bar and Favorite lists). These specific overlays are hard-wired exclusively to the physical Infrared (IR) hardware interrupts. 

We successfully mapped the remaining 95% of the remote control into the script, proving that the network protocol was fully conquered.

---

## Technical Summary of the Protocol

For developers looking to integrate this into other languages or platforms, here is the technical breakdown of the proprietary HiSilicon protocol we uncovered:

### 1. Pairing (Port 6467)
*   **Protocol:** Standard Google Polo Protocol.
*   **Quirk:** The TV strictly uses legacy **1024-bit RSA** certificates. Modern TLS clients will fail the handshake unless security levels are explicitly downgraded (e.g., `SECLEVEL=0`).

### 2. Control (Port 6466)
*   **Protocol:** Proprietary HiSilicon Binary Protocol over TLS.

**The Handshake Packet (22 bytes):**
Must be sent immediately upon connecting to port 6466.
*   `0x01` (1 byte: Message Type)
*   `0x00` (1 byte: Subtype)
*   `0x00 0x12` (2 bytes: Payload Length, always 18 bytes)
*   `0x00 0x00 0x00 0x01` (4 bytes)
*   `0x00 0x00 0x00 0x01` (4 bytes)
*   `0x20` (1 byte)
*   `0x03` (1 byte)
*   `0x00 0x00 0x00` (3 bytes: Padding)
*   `0x00 0x00 0x00 0x11` (4 bytes: String Length of MAC)
*   `[17 bytes]` (MAC Address string, e.g., `"aa:bb:cc:dd:ee:ff"`)

**The Key Injection Packet (20 bytes):**
Sent to inject keystrokes. Sent twice per keypress (once for ACTION_DOWN, once for ACTION_UP).
*   `0x01` (1 byte: Message Type)
*   `0x02` (1 byte: Subtype)
*   `0x00 0x10` (2 bytes: Payload Length, always 16 bytes)
*   `[8 bytes]` (Sequence Number / Timestamp as Long)
*   `[4 bytes]` (Action Type as Int: `0` for DOWN, `2` for UP)
*   `[4 bytes]` (Standard Android `KeyEvent` integer, e.g., `25`)

---

## Prerequisites & Setup

1. **Python 3.x**
2. **OpenSSL** (required to generate the legacy 1024-bit certificates).

Generate the required 1024-bit certificates by running:
```bash
openssl req -x509 -nodes -days 3650 -newkey rsa:1024 -keyout key1024.pem -out cert1024.pem
```
*(Keep `key1024.pem` and `cert1024.pem` in the same directory as the scripts).*

## Usage

### 1. Pairing the TV (`hisense_pair.py`)
Before sending remote commands, you must pair your computer with the TV. 
1. Ensure your TV is on and on the same Wi-Fi network.
2. Run the pairing script:
   ```bash
   python hisense_pair.py
   ```
3. A 4-digit hex code will appear on your TV screen. Type it into the terminal.
4. If successful, you will see `PAIRING SUCCESSFUL!`. (You only need to do this once).

### 2. Sending Remote Commands (`hisense_remote.py`)
Once paired, use `hisense_remote.py` to send keystrokes. You can use standard aliases or raw integer keycodes.

```bash
# Basic Navigation
python hisense_remote.py UP
python hisense_remote.py OK

# Volume Control
python hisense_remote.py VOL+
python hisense_remote.py MUTE

# Send raw Android KeyEvent integer
python hisense_remote.py 172
```

### Supported Key Aliases
| Category | Aliases |
| :--- | :--- |
| **Power/Inputs** | `POWER`, `STB`, `TV`, `SOURCE` |
| **Navigation** | `UP`, `DOWN`, `LEFT`, `RIGHT`, `OK`, `ENTER`, `BACK`, `EXIT`, `HOME`, `MENU`, `RECALL` |
| **Volume/Channels** | `VOL+`, `VOL-`, `MUTE`, `CH+`, `CH-` |
| **Media Controls**| `PLAY_PAUSE`, `STOP`, `RECORD`, `REWIND`, `FAST_FORWARD`, `PREVIOUS`, `NEXT` |
| **Colors** | `RED`, `GREEN`, `YELLOW`, `BLUE` |
| **Numbers** | `0` through `9` |
| **Misc** | `EPG`, `PLAYLIST`, `TELETEXT`, `SLEEP`, `SUBTITLE`, `RADIO/TV`, `PIP`, `RESOLUTION`, `CURSOR`, `V.FORMAT` |
