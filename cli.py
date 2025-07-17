"""
Examples demonstrating how to use the ZKE EBC-Axx electronic load interface.
This file demonstrates the command codes as shown in the protocol documentation.
"""

import argparse
import csv
import logging
import os
import sys
import time
from datetime import timedelta

from zke_ebc_axx.device import EBCDevice
from zke_ebc_axx.exceptions import CommunicationError


def setup_logging(debug_enabled=False, debug_file=None):
    """Set up logging configuration based on command-line arguments."""
    # Set up the base logger
    logger = logging.getLogger()
    logger.handlers.clear()  # Clear any existing handlers

    # Create a formatter for consistent output
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # Set up console handler - always show INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if debug_enabled:
        logger.setLevel(logging.DEBUG)

        if debug_file:
            # Debug to file
            file_handler = logging.FileHandler(debug_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        else:
            # Debug to console (lower console handler level to DEBUG)
            console_handler.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)


# Set up logging configuration
class Writer:
    def __init__(self, file):
        self.file = file
        self.csv_writer = None
        self.initialized = False

    def init(self, fieldnames):
        self.csv_writer = csv.DictWriter(self.file, fieldnames=fieldnames)
        self.csv_writer.writeheader()
        self.initialized = True

    def write(self, row):
        row["time"] = time.time()
        row.move_to_end("time", last=False)

        if not self.initialized:
            self.init(row.keys())
        logging.debug("Writing row: %s", row)
        self.csv_writer.writerow(row)
        self.file.flush()


def log_forever(device, writer):
    # Log data until the device is in a completed state
    while True:
        time.sleep(1)
        data = device.read_measurement()
        if not data:
            continue
        writer.write(data)


def handle_action(device, writer, args):
    """Handle the specified action."""
    if args.charge_cccv:
        logging.info("Starting charge CC-CV... Current: %sA, Voltage: %sV", args.current, args.voltage)
        device.charge_cccv(current=args.current, voltage=args.voltage, writer_cb=writer.write)
    elif args.charge_cv:
        logging.info("Starting charge CV... Voltage: %sV", args.voltage)
        device.charge_cv(target_voltage=args.voltage, writer_cb=writer.write)
    elif args.discharge_cc:
        logging.info("Starting discharge CC... Current: %sA, Cutoff: %sV", args.current, args.voltage)
        device.discharge_cc(current=args.current, cutoff_voltage=args.voltage, writer_cb=writer.write)
    elif args.discharge_cp:
        logging.info("Starting discharge CP... Power: %sW, Cutoff: %sV", args.power, args.voltage)
        device.discharge_cp(power=args.power, cutoff_voltage=args.voltage, writer_cb=writer.write)
    elif args.discharge_cv:
        logging.info("Starting discharge CV... Voltage: %sV", args.voltage)
        device.discharge_cv(target_voltage=args.voltage, writer_cb=writer.write)
    else:
        # Default to monitor mode
        logging.info("Starting monitoring mode...")
        log_forever(device, writer)


def main():
    parser = argparse.ArgumentParser(description="ZKE EBC-Axx Electronic Load CLI.")
    parser.add_argument("-o", "--output", help="Output CSV file (empty/absent for stdout)", default=None)
    parser.add_argument("-f", "--force", action="store_true", help="Force overwrite if output file exists")
    parser.add_argument(
        "-a", "--append", action="store_true", help="Append to output file instead of overwriting"
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--debug-file", help="Write debug logs to file (if not specified, debug goes to stdout)"
    )
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port device (default: /dev/ttyUSB0)")

    # Action flags (mutually exclusive)
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "-cccv", "--charge-cccv", action="store_true", help="Perform charge CC-CV operation"
    )
    action_group.add_argument("--charge-cv", action="store_true", help="Perform charge CV operation")
    action_group.add_argument(
        "-cc", "--discharge-cc", action="store_true", help="Perform discharge CC operation"
    )
    action_group.add_argument("--discharge-cp", action="store_true", help="Perform discharge CP operation")
    action_group.add_argument("--discharge-cv", action="store_true", help="Perform discharge CV operation")
    action_group.add_argument("--monitor", action="store_true", help="Monitor mode (default)")

    # Parameters for actions
    parser.add_argument("-c", "--current", type=float, default=1.0, help="Current in amperes (default: 1.0)")
    parser.add_argument("-v", "--voltage", type=float, default=4.0, help="Voltage in volts (default: 4.0)")
    parser.add_argument(
        "-p", "--power", type=float, default=5.0, help="Power in watts for CP discharge (default: 5.0)"
    )

    args = parser.parse_args()

    # Set up logging based on command-line arguments
    setup_logging(debug_enabled=args.debug, debug_file=args.debug_file)

    output_file = args.output

    # Check if output file exists and handle accordingly
    if output_file and os.path.exists(output_file) and not (args.force or args.append):
        print(
            f"Error: Output file '{output_file}' already exists. Use -f/--force to overwrite or -a/--append to append."
        )
        sys.exit(1)

    # Determine file mode based on append flag
    file_mode = "a" if args.append and output_file and os.path.exists(output_file) else "w"

    with open(output_file, file_mode, newline="") if output_file else sys.stdout as csvfile:
        writer = Writer(csvfile)

        device = EBCDevice(port=args.port, baudrate=9600, timeout=1.0)

        try:
            device.send_stop()
            time.sleep(1)
            handle_action(device, writer, args)
        except KeyboardInterrupt:
            logging.info("Operation interrupted by user")
            return
        except CommunicationError as e:
            logging.warning("Error: %s", e)
        finally:
            # Always disconnect properly
            device.send_stop()
            device.disconnect()


if __name__ == "__main__":
    main()
