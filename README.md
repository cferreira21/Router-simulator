# Network Router simulator

This project implements a router simulation for a computer networks assignment.

## router.py Overview

`router.py` is the main script that simulates the behavior of a network router. It is designed to:

- Parse network topology and configuration files.
- Manage routing tables and forwarding logic.
- Handle packet transmission and reception between interfaces.
- Support different network topologies, such as hub-and-spoke.
- Log events and trace packet flows for debugging and analysis.

### Main Features

- **Topology Parsing:** Reads configuration files to set up router interfaces and connections.
- **Routing Table Management:** Maintains and updates routing tables based on network changes.
- **Packet Forwarding:** Processes incoming packets and forwards them according to routing rules.
- **Simulation Support:** Can be used with provided test scripts to simulate various network scenarios.
- **Logging:** Outputs trace information for analysis and debugging.

### How to Use

1. Prepare the required configuration files (see `tests-public/hub-and-spoke/`).
2. Run the script with Python:
  ```powershell
  python router.py <config_file>
  ```
  Replace `<config_file>` with your topology or router configuration file.
3. Monitor the output for routing and packet trace information.

For more details on configuration formats and test scenarios, refer to the files in `tests-public/hub-and-spoke/` and the documentation in `tests-public/README.md`.

## Structure

- `router.py`: Main router simulation script.
- `tests-public/`: Public test resources and scripts.
  - `lo-addresses.sh`: Shell script for loopback address setup.
  - `README.md`: Documentation for public tests.
  - `hub-and-spoke/`: Example hub-and-spoke topology files.
    - `example-traces.txt`: Example trace outputs.
    - `hub.txt`: Hub configuration.
    - `spoke.txt`: Spoke configuration.
    - `tmux.sh`: Script for running tests in tmux.

## Usage

1. Ensure you have Python 3 installed.
2. Run the router simulation:
   ```powershell
   python router.py
   ```
3. Use the scripts in `tests-public/` to set up test environments and run example topologies.

## Notes
- This project is intended for educational purposes as part of a computer networks course.
- For more details on the tests, see `tests-public/README.md`.
