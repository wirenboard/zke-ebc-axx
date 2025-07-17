import binascii
import logging
import time
from collections import OrderedDict
from datetime import timedelta

import serial

from .constants import MODE
from .exceptions import CommandError, CommunicationError

# Configure logger
logger = logging.getLogger(__name__)


class EBCDevice:
    """
    Interface for ZKE EBC-Axx electronic loads and battery testers.
    """

    # Protocol constants
    INIT_BYTE = 0xFA  # First byte of each packet "FA"
    END_BYTE = 0xF8  # Last byte of each packet "F8"
    DEFAULT_TIMEOUT = 1.0  # Default timeout for responses
    COMMAND_LENGTH = 10  # Command is 10 bytes
    RESPONSE_LENGTH = 19  # Response is 19 bytes

    I_MULT = 1000  # internaly values are sent in mA
    V_MULT = 100  # internaly values are sent in 10mV
    P_MULT = 100  # internaly values are sent in 10mW

    # Modes nibbles
    MODE_SYS = 0x0
    MODE_D_CC = 0x0
    MODE_D_CP = 0x1
    MODE_C_NIMH = 0x2
    MODE_C_NICD = 0x3
    MODE_C_LIPO = 0x4
    MODE_C_LIFE = 0x5
    MODE_C_PB = 0x6
    MODE_C_CCCV = 0x7

    MODE_NAMES = {
        MODE_SYS: "SYS",
        MODE_D_CC: "D_CC",
        MODE_D_CP: "D_CP",
        MODE_C_NIMH: "C_NIMH",
        MODE_C_NICD: "C_NICD",
        MODE_C_LIPO: "C_LIPO",
        MODE_C_LIFE: "C_LIFE",
        MODE_C_PB: "C_PB",
        MODE_C_CCCV: "C_CCCV",
    }

    RESP_STATE_IDLE = 0
    RESP_STATE_WORKING = 1
    RESP_STATE_COMPLETED = 2

    RESP_STATE_NAMES = {
        RESP_STATE_IDLE: "IDLE",
        RESP_STATE_WORKING: "WORKING",
        RESP_STATE_COMPLETED: "COMPLETED",
    }

    # Command nibbles from the documentation
    # sys commands, payload is zeroes
    CMD_CONNECT = 0x05
    CMD_DISCONNECT = 0x06
    CMD_STOP = 0x02

    # Charge/discharge control commands
    CMD_START = 0x01
    CMD_ADJUST = 0x07
    CMD_CONTINUE = 0x08

    def __init__(self, port, baudrate=9600, timeout=1.0):
        """
        Initialize the EBC device.


        Args:
            port (str): Serial port (e.g., 'COM1', '/dev/ttyUSB0')
            baudrate (int): Communication baud rateCURRENT_MULTIPLIER
        """
        self.baudrate = baudrate
        self.port = port
        self.timeout = timeout
        self._ser = None
        logger.info("Initializing EBC device on port %s with baudrate %d", port, baudrate)
        self.connect()

    def connect(self):
        """Establish connection to the device."""
        try:
            logger.debug("Attempting to connect to %s", self.port)
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity="E",
                stopbits=1,
                timeout=self.timeout,
                rtscts=False,
            )
            time.sleep(0.5)  # Allow time for device to initialize

            self.send_command(self.MODE_SYS, self.CMD_CONNECT)
            time.sleep(0.5)

            logger.info("Successfully connected to device on %s", self.port)
        except serial.SerialException as e:
            logger.error("Connection failed: %s", e)
            raise CommunicationError(f"Failed to connect to device: {e}")

    def disconnect(self):
        """Close the connection."""
        if self._ser and self._ser.is_open:
            logger.debug("Disconnecting from device")
            self.send_command(self.MODE_SYS, self.CMD_DISCONNECT)
            self._ser.close()
            logger.info("Device disconnected")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.send_stop()
        self.disconnect()

    def _calculate_checksum(self, data):
        """
        Calculate checksum for command/response data.
        Checksum is XOR of bytes 2-9 (for commands) or 2-18 (for responses).
        Note: Initial byte (FA) and terminal byte (F8) are not included in calculation.

        Args:
            data (bytes): The data bytes for which to calculate checksum

        Returns:
            int: The calculated checksum byte
        """
        result = 0
        for byte in data:
            result ^= byte
        return result

    def send_command(self, mode, command, data=None):
        """
        Send a command to the device following the protocol specification.

        Args:
            mode (int): The mode nibble
            command (int): The command nibble (COP)
            data (bytes): Data bytes (default is all zeros)

        Raises:
            CommunicationError: If communication fails
        """
        if not self._ser or not self._ser.is_open:
            logger.error("Cannot send command - device is not connected")
            raise CommunicationError("Device is not connected")

        if not (0 <= mode <= 0xF):
            logger.error("Invalid mode code: %s", mode)
            raise CommandError(f"Invalid mode code: {mode}")
        if not (0 <= command <= 0xF):
            logger.error("Invalid command code: %s", command)
            raise CommandError(f"Invalid command code: {command}")
        command_code = (mode << 4) | command

        # Initialize data bytes if not provided
        if data is None:
            data_list = [0] * 6  # 6 data bytes
        else:
            # Convert bytes to list and ensure proper length
            data_list = list(data)
            if len(data_list) < 6:
                data_list = data_list + [0] * (6 - len(data_list))  # Pad with zeros
            elif len(data_list) > 6:
                data_list = data_list[:6]  # Truncate to 6 bytes

        # Construct command packet
        # Format: [InitByte, COP, Data1, Data2, Data3, Data4, Data5, Data6, ChSum, EndByte]
        cmd_bytes = [self.INIT_BYTE, command_code] + data_list

        # Calculate checksum (XOR of bytes 2-9)
        checksum = self._calculate_checksum(cmd_bytes[1:8])
        cmd_bytes.append(checksum)
        cmd_bytes.append(self.END_BYTE)

        try:
            # Send the command
            cmd_packet = bytes(cmd_bytes)
            logger.debug("Sending command: 0x%02X, data: %s", command_code, [hex(b) for b in data_list])
            logger.debug("Full packet: %s", [hex(b) for b in cmd_packet])
            self._ser.write(cmd_packet)
            logger.info("Command 0x%02X sent successfully", command_code)
            time.sleep(0.1)  # Allow time for device to process command
        except serial.SerialException as e:
            logger.error("Failed to send command: %s", e)
            raise CommunicationError(f"Communication error: {e}")

    def send_command_16bit(self, mode, command, arg1=0, arg2=0, arg3=0):
        """
        Send a command with 16-bit arguments to the device.

        Args:
            mode (int): The mode nibble
            command (int): The command nibble (COP)
            arg1 (int): First argument (0-57599)
            arg2 (int): Second argument (0-57599)
            arg3 (int): Third argument (0-57599)

        Raises:
            CommunicationError: If communication fails
        """
        # Encode the arguments
        encoded_args = self.encode_value(arg1) + self.encode_value(arg2) + self.encode_value(arg3)
        return self.send_command(mode, command, encoded_args)

    def send_stop(self):
        """
        Send a stop command to the device.
        This command is used to stop any ongoing operation.

        Raises:
            CommunicationError: If communication fails
        """
        logger.debug("Sending stop command")
        return self.send_command(self.MODE_SYS, self.CMD_STOP)

    def encode_value(self, value):
        """
        Encodes a 16-bit value according to the protocol requirements.
        The encoding ensures that no data bytes fall within the range of protocol identifiers (F0h-FFh).

        The encoding algorithm:
        1. For values 0-239: Value is unchanged
        2. For values >= 240: Add an offset of 16 for each increment of 240 in the value range

        Args:
            value (int): Original value to encode (0-57599)

        Returns:
            bytes: Two bytes representing the encoded value (MSB, LSB)

        Raises:
            ValueError: If the value is outside the valid range (0-57599)
        """
        if not 0 <= value <= 57599:
            raise ValueError(f"Value must be between 0 and 57599, got {value}")

        # Calculate the offset group
        offset_group = value // 240

        if offset_group == 0:
            # Values 0-239 remain unchanged
            encoded_value = value
        else:
            # For values ≥240, apply an offset of 16 for each group
            offset = offset_group * 16
            encoded_value = value + offset

        # Calculate the two bytes (MSB, LSB)
        msb = (encoded_value >> 8) & 0xFF
        lsb = encoded_value & 0xFF

        logger.debug("Encoded value %d to bytes: 0x%02X, 0x%02X", value, msb, lsb)
        return bytes([msb, lsb])

    def decode_value(self, data):
        """
        Decodes two bytes according to the protocol requirements,
        reversing the encoding performed by encode_value.

        Args:
            data (bytes): Two bytes representing the encoded value (MSB, LSB)

        Returns:
            int: The decoded original value (0-57599)

        Raises:
            ValueError: If the encoded bytes represent an invalid value or if data length is not 2
        """
        if len(data) != 2:
            raise ValueError(f"Data must be exactly 2 bytes, got {len(data)} bytes")

        msb, lsb = data[0], data[1]

        # Combine the two bytes
        encoded_value = (msb << 8) | lsb
        decoded_value = encoded_value - msb * 16

        logger.debug("Decoded bytes 0x%02X, 0x%02X to value %d", msb, lsb, decoded_value)
        return decoded_value

    def _send_cmd_charge_predefined(self, mode, cmd, current, ncells, timeout):
        if mode not in [
            self.MODE_C_NIMH,
            self.MODE_C_NICD,
            self.MODE_C_LIPO,
            self.MODE_C_LIFE,
            self.MODE_C_PB,
        ]:
            raise ValueError("Invalid mode for charge operation")

        self.send_command_16bit(
            mode,
            cmd,
            int(current * self.I_MULT),
            ncells,
            int(timeout.total_seconds() / 60),
        )

    def start_charge_predefined(self, mode, current, ncells=1, timeout=timedelta(0)):
        """
        Start a battery charge operation with predefined parameters for a given chemistry.
        Args:
            mode (int): The mode nibble (e.g., MODE_C_LIPO)
            current (int): Charge current in A
            ncells (int): Number of cells in series
            timeout (timedelta): Timeout for the operation
        """
        self._send_cmd_charge_predefined(mode, self.CMD_START, current, ncells, timeout)

    def adjust_charge_predefined(self, mode, current, ncells=1, timeout=timedelta(0)):
        """
        Adjust a battery charge operation with predefined parameters for a given chemistry.
        Args:
            mode (int): The mode nibble (e.g., MODE_C_LIPO)
            current (int): Charge current in A
            ncells (int): Number of cells in series
            timeout (timedelta): Timeout for the operation
        """
        self._send_cmd_charge_predefined(mode, self.CMD_ADJUST, current, ncells, timeout)

    def _send_cmd_charge_cccv(self, cmd, voltage, current, timeout):
        self.send_command_16bit(
            self.MODE_C_CCCV,
            cmd,
            int(current * self.I_MULT),
            int(voltage * self.V_MULT),
            int(timeout.total_seconds() / 60),
        )

    def start_charge_cccv(self, voltage, current, timeout=timedelta(0)):
        """
        Start a charge operation with CCCV mode.
        Args:
            voltage (int): Charge voltage in V
            current (int): Charge current in A
            timeout (timedelta): Timeout for the operation
        """

        return self._send_cmd_charge_cccv(self.CMD_START, voltage, current, timeout)

    def adjust_charge_cccv(self, voltage, current, timeout=timedelta(0)):
        """
        Adjust a charge operation with CCCV mode.
        Args:
            voltage (int): Charge voltage in V
            current (int): Charge current in A
            timeout (timedelta): Timeout for the operation
        """

        return self._send_cmd_charge_cccv(self.CMD_ADJUST, voltage, current, timeout)

    def _send_cmd_discharge_cc(self, cmd, current, cutoff_voltage, timeout):
        self.send_command_16bit(
            self.MODE_D_CC,
            self.CMD_START,
            int(current * self.I_MULT),
            int(cutoff_voltage * self.V_MULT),
            int(timeout.total_seconds() / 60),
        )

    def start_discharge_cc(self, current, cutoff_voltage, timeout=timedelta(0)):
        """
        Start a discharge operation with constant current.
        Args:
            current (int): Discharge current in A
            cutoff_voltage (int): Cutoff voltage in V
            timeout (timedelta): Timeout for the operation
        """
        return self._send_cmd_discharge_cc(self.CMD_START, current, cutoff_voltage, timeout)

    def adjust_discharge_cc(self, current, cutoff_voltage, timeout=timedelta(0)):
        """
        Adjust a discharge operation with constant current.
        Args:
            current (int): Discharge current in A
            cutoff_voltage (int): Cutoff voltage in V
            timeout (timedelta): Timeout for the operation
        """

        return self._send_cmd_discharge_cc(self.CMD_ADJUST, current, cutoff_voltage, timeout)

    def _send_cmd_discharge_cp(self, cmd, power, cutoff_voltage, timeout):
        self.send_command_16bit(
            self.MODE_D_CC,
            cmd,
            int(power * self.P_MULT),
            int(cutoff_voltage * self.V_MULT),
            int(timeout.total_seconds() / 60),
        )

    def start_discharge_cp(self, power, cutoff_voltage, timeout=timedelta(0)):
        """
        Start a discharge operation with constant current.
        Args:
            current (int): Discharge current in A
            cutoff_voltage (int): Cutoff voltage in V
            timeout (timedelta): Timeout for the operation
        """

        return self._send_cmd_discharge_cp(self.CMD_START, power, cutoff_voltage, timeout)

    def adjust_discharge_cp(self, power, cutoff_voltage, timeout=timedelta(0)):
        """
        Adjust a discharge operation with constant current.
        Args:
            current (int): Discharge current in A
            cutoff_voltage (int): Cutoff voltage in V
            timeout (timedelta): Timeout for the operation
        """

        return self._send_cmd_discharge_cp(self.CMD_ADJUST, power, cutoff_voltage, timeout)

    def discard_unread(self):
        """
        Discard unread data from the serial buffer.
        This is useful to clear any unwanted data before reading a new measurement.
        """
        if self._ser and self._ser.is_open:
            logger.debug("Discarding unread data from serial buffer")
            self._ser.reset_input_buffer()

    def read_measurement(self):
        """
        Read a measurement from the device.
        """

        data = self._ser.read(self.RESPONSE_LENGTH)
        logging.debug("Received data: %s", binascii.hexlify(data).decode("ascii"))
        if not data:
            return None

        if len(data) != self.RESPONSE_LENGTH:
            logger.error("Invalid response length: expected %d, got %d", self.RESPONSE_LENGTH, len(data))
            return None

        if data[0] != self.INIT_BYTE or data[-1] != self.END_BYTE:
            logger.error(
                "Invalid response format: expected %02X...%02X, got %s", self.INIT_BYTE, self.END_BYTE, data
            )
            return None

        checksum = data[17]
        # Checksum is XOR of bytes 2-18 (excluding init and end byte)
        calculated_checksum = self._calculate_checksum(data[1:-2])
        if checksum != calculated_checksum:
            logger.warning("Checksum mismatch: expected %02X, got %02X", calculated_checksum, checksum)
            # raise CommandError(f"Checksum mismatch: expected {calculated_checksum}, got {checksum}")

        # Decode regime
        regime = data[1]
        mode = regime % 10
        mode_str = self.MODE_NAMES.get(mode, f"UNKNOWN_{mode}")
        state = regime // 10
        state_str = self.RESP_STATE_NAMES.get(state, f"UNKNOWN_{state}")

        i_measured = self.decode_value(data[2:4])
        u_measured = self.decode_value(data[4:6])
        stored_charge = self.decode_value(data[6:8])
        unk1 = data[8:10].hex()  # Unknown bytes (always 0000h)

        # DATA setting
        i_setting = self.decode_value(data[10:12])
        u_cutoff = self.decode_value(data[12:14])
        max_time = self.decode_value(data[14:16])

        # Seems to be identification/model (always 05h according to the image)
        ident = data[16]

        return OrderedDict(
            [
                ("regime", f"{regime:02x}"),
                ("mode", mode_str),
                ("state", state_str),
                ("i_measured", i_measured / 1000.0),  # Assuming the value is in 0.0001A units
                ("u_measured", u_measured / 1000.0),  # Assuming the value is in 0.001V units
                ("stored_charge", stored_charge),
                ("i_setting", i_setting / 1000.0),  # Assuming the value is in 0.001A units
                ("u_cutoff", u_cutoff / 100.0),  # Assuming the value is in 0.001V units
                ("max_time", max_time),
                ("ident", f"{ident:02x}"),
                ("unk1", unk1),
                ("raw_data", data.hex()),
            ]
        )

    def read_until_complete(self, writer_cb=None):
        self.discard_unread()
        counter = 0
        while counter < 4:
            time.sleep(1)
            data = self.read_measurement()
            if not data:
                continue
            logging.debug("Got data: %s", data)
            if writer_cb is not None:
                writer_cb(data)
            if data["state"] in ("COMPLETED", "IDLE"):
                counter += 1

    def charge_cccv(self, voltage, current, timeout=timedelta(0), writer_cb=None):
        """
        Charge the battery using CCCV mode.
        This function starts a charge operation with the specified voltage and current,
        and continuously reads measurements until the operation is completed (or interrupted).
        Args:
            voltage (float): Charge voltage in Volts
            current (float): Charge current in Amperes
            timeout (timedelta): Timeout for the operation
            writer_cb (callable, optional): Callback function to write data during charging
        """
        self.start_charge_cccv(voltage=voltage, current=current, timeout=timeout)
        time.sleep(2.5)
        self.discard_unread()
        self.read_until_complete(writer_cb=writer_cb)

    def discharge_cc(self, current, cutoff_voltage, timeout=timedelta(0), writer_cb=None):
        """
        Discharge the battery using constant current mode.
        This function starts a discharge operation with the specified current and cutoff voltage,
        and continuously reads measurements until the operation is completed (or interrupted).
        Args:
            current (float): Discharge current in Amperes
            cutoff_voltage (float): Cutoff voltage in Volts
            timeout (timedelta): Timeout for the operation
            writer_cb (callable, optional): Callback function to write data during discharging
        """
        self.start_discharge_cc(current=current, cutoff_voltage=cutoff_voltage, timeout=timeout)
        time.sleep(2.5)
        self.discard_unread()
        self.read_until_complete(writer_cb=writer_cb)

    def discharge_cp(self, power, cutoff_voltage, timeout=timedelta(0), writer_cb=None):
        """
        Discharge the battery using constant power mode.
        This function starts a discharge operation with the specified power and cutoff voltage,
        and continuously reads measurements until the operation is completed (or interrupted).
        Args:
            power (float): Discharge power in Watts
            cutoff_voltage (float): Cutoff voltage in Volts
            timeout (timedelta): Timeout for the operation
            writer_cb (callable, optional): Callback function to write data during discharging
        """
        self.start_discharge_cp(power=power, cutoff_voltage=cutoff_voltage, timeout=timeout)
        time.sleep(2.5)
        self.discard_unread()
        self.read_until_complete(writer_cb=writer_cb)

    def discharge_cv(self, target_voltage, writer_cb=None):
        """
        Helper function to discharge the device to a target voltage using CC mode.
        The current is lowered dynamically till zero until the target voltage is reached.
        Args:
            target_voltage (float): Target voltage to discharge to in Volts
            writer_cb (callable, optional): Callback function to write data during discharge
        """
        current = 5
        self.discard_unread()
        while 1:
            data = self.read_measurement()
            if not data:
                continue
            if data["u_measured"] < target_voltage:
                logging.warning("Voltage %.3fV is already below target %.3fV", data["u_measured"], target_voltage)
                return
            break

        logging.info("Starting discharge to %.3fV with initial current %.3fA", target_voltage, current)
        self.start_discharge_cc(current, target_voltage)
        time.sleep(2.5)
        self.discard_unread()

        while 1:
            time.sleep(1)
            data = self.read_measurement()
            if not data:
                continue
            if writer_cb:
                writer_cb(data)
            if data["state"] in ("COMPLETED", "IDLE"):
                current *= 0.8
                if current < 0.05:
                    break
                logging.info("Adjusting discharge current to %.3fA", current)
                self.adjust_discharge_cc(current, target_voltage)
                time.sleep(2.5)
                self.discard_unread()
        return

    def charge_cv(self, target_voltage, writer_cb=None):
        """
        Helper function to charge the device to a target voltage using CCCV mode.
        The current is lowered dynamically till zero until the target voltage is reached.
        Args:
            target_voltage (float): Target voltage to charge to in Volts
            writer_cb (callable, optional): Callback function to write data during charging
        """
        current = 5
        self.discard_unread()
        while 1:
            data = self.read_measurement()
            if not data:
                continue
            if data["u_measured"] > target_voltage:
                logging.warning("Voltage %.3fV is already above target %.3fV", data["u_measured"], target_voltage)
                return
            break

        logging.info("Starting charge to %.3fV with initial current %.3fA", target_voltage, current)
        self.start_charge_cccv(voltage=target_voltage, current=current)
        time.sleep(2.5)
        self.discard_unread()

        while 1:
            time.sleep(1)
            data = self.read_measurement()
            if not data:
                continue
            if writer_cb:
                writer_cb(data)
            if data["state"] in ("COMPLETED", "IDLE"):
                current *= 0.8
                if current < 0.05:
                    break
                logging.info("Adjusting charge current to %.3fA", current)
                self.adjust_charge_cccv(voltage=target_voltage, current=current)
                time.sleep(2.5)
                self.discard_unread()
        return
