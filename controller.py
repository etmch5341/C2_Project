import socket
import hmac
import hashlib
import os
import sys

HOST = "0.0.0.0"
PORT = 4444
SECRET = "my_shared_key"


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
        # print("in exception")
        return False


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)

    print(f"[+] Listening on port {PORT}...")

    while True:
        conn, addr = server.accept()
        # print(f"[+] Connection from {addr}")

        if not authenticate(conn, SECRET):
            print("[-] Authentication failed")
            conn.close()
            continue

        command = input("> ").strip()

        if not command:
            # print("[!] Empty command, try again")
            conn.close()
            continue
        
        if command.lower() == "exit":
            print("[*] Closing connection")
            sys.exit(0)

        conn.sendall(command.encode())

        output = conn.recv(8192)

        if not output:
            print("[-] No response")
        else:
            print(output.decode())

        conn.close()


if __name__ == "__main__":
    main()