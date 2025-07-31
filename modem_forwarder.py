DEBUG_MODEM = True
#!/usr/bin/env python3

import serial
import socket
import selectors
import time
import sys

MODEM_PORT = "/dev/ttyUSB0"
BAUDRATE = 2400
TELNET_HOST = "bbs.c64.pub"
TELNET_PORT = 64

# Tunables
MODEM_READ_CHUNK = 1          # responsive
BBS_READ_CHUNK = 1024
SERIAL_TIMEOUT = 0            # non-blocking
HANGUP_READ_TIMEOUT = 0.5     # wait for OK/NO CARRIER after hangup

def force_hangup(ser):
    """
    Force the modem to drop any existing connection: DTR toggle, escape, ATH.
    Waits briefly for 'OK' or 'NO CARRIER'.
    """
    print("[INFO] Forcing hangup: DTR drop + escape + ATH")
    try:
        # Hard drop via DTR toggle
        ser.dtr = False
        if DEBUG_MODEM:
            print("[DEBUG] DTR set to False")
        time.sleep(1)
        ser.dtr = True
        if DEBUG_MODEM:
            print("[DEBUG] DTR set to True")
        time.sleep(0.5)

        # Guard time before escape
        time.sleep(0.5)
        if DEBUG_MODEM:
            print(f"[DEBUG] Writing to modem: b'+++'")
        ser.write(b"+++")
        ser.flush()
        time.sleep(1)

        # Hang up
        if DEBUG_MODEM:
            print(f"[DEBUG] Writing to modem: b'ATH\\r'")
        ser.write(b"ATH\r")
        ser.flush()

        # Wait for acknowledgement, up to 5 seconds
        deadline = time.time() + 5.0
        resp = ""
        while time.time() < deadline:
            waiting = ser.in_waiting
            if waiting:
                if DEBUG_MODEM:
                    print(f"[DEBUG] Reading {waiting} bytes from modem during hangup wait")
                chunk = ser.read(waiting)
                if DEBUG_MODEM:
                    print(f"[DEBUG] Read bytes: {chunk!r}")
                chunk_decoded = chunk.decode(errors="ignore")
                resp += chunk_decoded
                if "OK" in resp.upper() or "NO CARRIER" in resp.upper():
                    print(f"[INFO] Hangup response: {resp.strip()!r}")
                    return
            time.sleep(0.05)
        print(f"[WARN] Hangup timeout, last response: {resp.strip()!r}")
    except Exception as e:
        print(f"[ERROR] force_hangup exception: {e}")

def init_modem(ser):
    print("[INFO] Initializing modem...")
    sequence = [b"ATZ\r", b"AT&D0\r", b"AT&C0\r", b"ATV1\r", b"ATS0=1\r"]
    for cmd in sequence:
        ser.write(cmd)
        ser.flush()
        time.sleep(1)

def wait_for_connect(ser):
    print("[INFO] Waiting for incoming call...")
    buffer = ""
    while True:
        waiting = ser.in_waiting
        if waiting:
            if DEBUG_MODEM:
                print(f"[DEBUG] Reading {waiting} bytes from modem during connect wait")
            data = ser.read(waiting)
            if DEBUG_MODEM:
                print(f"[DEBUG] Read bytes: {data!r}")
            data_decoded = data.decode(errors="ignore")
            print(f"Modem says: {data_decoded.strip()}")
            buffer += data_decoded.upper()
            if "CONNECT" in buffer:
                print("[INFO] CONNECT detected!")
                try:
                    modem_print(ser, "Hello World")
                except Exception as e:
                    print(f"[ERROR] sending greeting to modem: {e}")
                # Flush input buffer to ignore any previous input (do this ONCE before prompting)
                if hasattr(ser, 'reset_input_buffer'):
                    if DEBUG_MODEM:
                        print("[DEBUG] Flushing modem input buffer (reset_input_buffer)")
                    ser.reset_input_buffer()
                else:
                    if DEBUG_MODEM:
                        print("[DEBUG] Flushing modem input buffer (flushInput)")
                    ser.flushInput()
                time.sleep(0.1)  # Let any noise settle
                # Drain any remaining characters in the buffer
                while ser.in_waiting:
                    waiting = ser.in_waiting
                    if DEBUG_MODEM:
                        print(f"[DEBUG] Draining {waiting} bytes from modem input buffer")
                    _ = ser.read(waiting)
                print("[INFO] Waiting for 'C' from modem to continue...")
                modem_print(ser, "Hit 'C' to connect.")
                while True:
                    ch = modem_getch(ser)
                    if ch.upper() == b'C':
                        print("[INFO] 'C' received, continuing to bridge session.")
                        break
                return
        time.sleep(0.05)

def bridge_session(ser):
    print(f"[INFO] Connecting to Telnet server {TELNET_HOST}:{TELNET_PORT}...")
    try:
        sock = socket.create_connection((TELNET_HOST, TELNET_PORT), timeout=10)
    except Exception as e:
        print(f"[ERROR] Could not connect to Telnet server: {e}")
        return

    sock.setblocking(False)
    sel = selectors.DefaultSelector()
    sel.register(ser, selectors.EVENT_READ, data="modem")
    sel.register(sock, selectors.EVENT_READ, data="bbs")

    print("[INFO] Telnet connected. Entering bridge loop...")

    try:
        while True:
            events = sel.select(1)
            if not events:
                continue

            for key, mask in events:
                source = key.data
                if source == "modem":
                    try:
                        data = ser.read(ser.in_waiting or MODEM_READ_CHUNK)
                    except Exception as e:
                        print(f"[ERROR] reading modem: {e}")
                        data = b""
                    if data:
                        print(f"[Modem→Telnet] {len(data)} bytes →: {data[:80]!r}")
                        try:
                            sock.sendall(data)
                        except Exception as e:
                            print(f"[ERROR] send to BBS failed: {e}")
                            return
                elif source == "bbs":
                    try:
                        data = sock.recv(BBS_READ_CHUNK)
                    except BlockingIOError:
                        data = b""
                    except Exception as e:
                        print(f"[ERROR] reading bbs: {e}")
                        data = b""
                    if data:
                        print(f"[Telnet→Modem] {len(data)} bytes ←: {data[:80]!r}")
                        try:
                            ser.write(data)
                            ser.flush()
                            # # Simulate output speed for current baud rate
                            # bytes_per_sec = BAUDRATE / 10.0
                            # time.sleep(len(data) / bytes_per_sec)
                        except Exception as e:
                            print(f"[ERROR] write to modem failed: {e}")
                            return
                    elif data == b"":
                        # Remote side closed
                        print("[INFO] BBS closed connection. Ending session.")
                        return
    finally:
        try:
            sel.unregister(ser)
            sel.unregister(sock)
        except Exception:
            pass
        sock.close()
        print("[INFO] Bridge loop exited, forcing hangup.")
        force_hangup(ser)


def modem_print(ser, text):
    """
    Send a string to the modem, appending CRLF, and flush.
    """
    if not text.endswith("\r\n"):
        text = text + "\r\n"
    btext = text.encode(errors="replace")
    if DEBUG_MODEM:
        print(f"[DEBUG] Writing to modem: {btext!r}")
    ser.write(btext)
    ser.flush()


def modem_input(ser, prompt=None):
    """
    Optionally send a prompt, then read and return a line of input from the modem (ending with CR or LF, line ending stripped).
    """
    if prompt:
        modem_print(ser, prompt)
    buf = b""
    while True:
        waiting = ser.in_waiting
        if waiting:
            if DEBUG_MODEM:
                print(f"[DEBUG] Reading {waiting} bytes from modem during modem_input")
            ch = ser.read(1)
            if DEBUG_MODEM:
                print(f"[DEBUG] Read byte: {ch!r}")
            if ch in (b'\r', b'\n'):
                if buf:
                    break
                else:
                    continue  # ignore leading newlines
            buf += ch
        else:
            time.sleep(0.05)
    return buf.decode(errors="replace")


def modem_getch(ser, prompt=None):
    """
    Optionally send a prompt, then wait for and return a single character from the modem (no Enter required).
    """
    if prompt:
        modem_print(ser, prompt)
    while True:
        waiting = ser.in_waiting
        if waiting:
            if DEBUG_MODEM:
                print(f"[DEBUG] Reading {waiting} bytes from modem during modem_getch")
            ch = ser.read(1)
            if DEBUG_MODEM:
                print(f"[DEBUG] Read byte: {ch!r}")
            return ch
        time.sleep(0.05)


def main_loop():
    while True:
        try:
            with serial.Serial(MODEM_PORT, BAUDRATE, timeout=SERIAL_TIMEOUT) as ser:
                ser.dtr = True
                ser.xonxoff = True
                # ensure clean state before init
                force_hangup(ser)
                init_modem(ser)
                wait_for_connect(ser)
                bridge_session(ser)
                # post-session hangup (redundant with bridge_session cleanup)
                force_hangup(ser)
                time.sleep(1)
        except serial.SerialException as e:
            print(f"[ERROR] Serial error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("Interrupted, exiting.")
            sys.exit(0)

if __name__ == "__main__":
    main_loop()