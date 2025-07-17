# ZKE EBC-Axx Python Package

A Python interface for ZKE EBC-Axx series electronic loads and battery testers.

## Features

- Direct control of ZKE EBC-Axx series devices
- Support for all operation modes: CC, CV, CR, CP, and Battery Testing
- Simple high-level interface for common operations
- Comprehensive error handling
- Example scripts for basic usage and battery testing

## Installation

```bash
# Install from the local directory
pip install -e .

# Or install directly from GitHub
pip install git+https://github.com/yourusername/zke_ebc_axx.git
```

## Requirements

- Python 3.6 or higher
- pyserial 3.4 or higher

## Usage

### Basic Example

```python
from zke_ebc_axx import EBCDevice, MODE

# Connect to the device
with EBCDevice('/dev/ttyUSB0') as device:
    # Get device identity
    print(f"Connected to: {device.get_identity()}")
    
    # Set to constant current mode
    device.set_mode(MODE.CC)
    
    # Set current to 1A
    device.set_current(1.0)
    
    # Turn output on
    device.output_on()
    
    # Get measurements
    measurements = device.get_measurements()
    print(f"Voltage: {measurements['voltage']}V")
    print(f"Current: {measurements['current']}A")
    print(f"Power: {measurements['power']}W")
    
    # Turn output off
    device.output_off()
```

### Battery Testing

```python
from zke_ebc_axx import EBCDevice

with EBCDevice('/dev/ttyUSB0') as device:
    # Start battery test with 3.0V cutoff and 0.5A discharge
    device.start_battery_test(cutoff_voltage=3.0, discharge_current=0.5)
    
    # Monitor the test
    status = device.get_battery_status()
    print(f"Voltage: {status['voltage']}V")
    print(f"Capacity: {status['capacity']}Ah")
    
    # Stop the test
    device.stop_battery_test()
```

## API Reference

See the example scripts in the `examples` directory for more detailed usage.

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
