import serial
import requests
import json
import os
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Union, Iterator, Tuple
from dataclasses import dataclass
import re
import platform
import subprocess
import webbrowser
from urllib.parse import urlparse

# NOR File offsets
OFFSET_ONE = 0x1c7010
OFFSET_TWO = 0x1c7030
WIFI_MAC_OFFSET = 0x1C73C0
LAN_MAC_OFFSET = 0x1C4020
SERIAL_OFFSET = 0x1c7210
VARIANT_OFFSET = 0x1c7226
MOBO_SERIAL_OFFSET = 0x1C7200

@dataclass
class UartError(Exception):
    """Custom exception for UART operations"""
    message: str
    details: Optional[str] = None

class UartHandler:
    def __init__(self):
        self.connection: Optional[serial.Serial] = None
        self.error_codes_db: Dict[str, str] = {}
        self.db_path: str = os.path.join(os.path.dirname(__file__), '..', 'resources', 'error_codes.xml')
        self.initialize_error_database()
    
    def validate_nor_file(self, nor_data: bytes) -> bool:
        """
        Validate if the provided data is a valid PS5 NOR dump
        
        Args:
            nor_data: NOR file data to validate
            
        Returns:
            bool: True if valid, False otherwise
            
        Raises:
            UartError: If validation fails
        """
        try:
            # Check minimum size
            if len(nor_data) < max(OFFSET_ONE, OFFSET_TWO, WIFI_MAC_OFFSET, LAN_MAC_OFFSET, SERIAL_OFFSET, VARIANT_OFFSET, MOBO_SERIAL_OFFSET) + 16:
                return False
                
            # Check if we can read the version info
            version = nor_data[OFFSET_ONE:OFFSET_ONE + 16].decode('ascii', errors='ignore').strip('\x00')
            variant = nor_data[OFFSET_TWO:OFFSET_TWO + 16].decode('ascii', errors='ignore').strip('\x00')
            
            # Basic validation - version and variant should be readable
            return bool(version and variant)
        except Exception as e:
            raise UartError("Failed to validate NOR file", str(e))
    
    def initialize_error_database(self) -> bool:
        """
        Initialize error code database by downloading if not exists
        
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            UartError: If initialization fails
        """
        try:
            if not os.path.exists(self.db_path):
                return self.download_error_database()
            return True
        except Exception as e:
            raise UartError("Failed to initialize error database", str(e))
    
    def handle_error_response(self, response: str) -> str:
        """
        Handle error response from UART device
        
        Args:
            response: Response from UART device
            
        Returns:
            str: Formatted error message
            
        Raises:
            UartError: If response parsing fails
        """
        try:
            if response.startswith("ERROR:"):
                codes = response[6:].split(',')
                error_messages = []
                for code in codes:
                    code = code.strip()
                    if self.validate_error_code(code):
                        desc = self.get_error_description(code)
                        error_messages.append(f"Error code: {code}\nDescription: {desc}")
                return "\n\n".join(error_messages)
            return response
        except Exception as e:
            raise UartError("Failed to handle error response", str(e))
    
    def calculate_checksum(self, data: str) -> str:
        """
        Calculate checksum for a string
        
        Args:
            data: String to calculate checksum for
            
        Returns:
            str: Original string with checksum appended
        """
        checksum = sum(ord(c) for c in data) & 0xFF
        return f"{data}:{checksum:02X}"
    
    def hex_string_to_string(self, hex_string: str) -> str:
        """
        Convert hex string to regular string
        
        Args:
            hex_string: Hex string to convert
            
        Returns:
            str: Converted string
            
        Raises:
            UartError: If hex string is invalid
        """
        if not hex_string or len(hex_string) % 2 != 0:
            raise UartError("Invalid hex string")
        
        try:
            return bytes.fromhex(hex_string).decode('ascii')
        except Exception as e:
            raise UartError("Failed to convert hex string", str(e))
    
    def string_to_hex_string(self, text: str) -> str:
        """
        Convert string to hex string
        
        Args:
            text: String to convert
            
        Returns:
            str: Hex representation of string
        """
        return ''.join(f"{ord(c):02X}" for c in text)
    
    def hex_string_to_bytes(self, hex_string: str) -> bytes:
        """
        Convert hex string to byte array
        
        Args:
            hex_string: Hex string to convert
            
        Returns:
            bytes: Byte array representation
            
        Raises:
            UartError: If hex string is invalid
        """
        if not hex_string or len(hex_string) % 2 != 0:
            raise UartError("Invalid hex string")
        
        try:
            return bytes.fromhex(hex_string)
        except Exception as e:
            raise UartError("Failed to convert hex string to bytes", str(e))
    
    def find_pattern(self, source: bytes, pattern: bytes) -> Iterator[int]:
        """
        Find all occurrences of a pattern in a byte array
        
        Args:
            source: Source byte array to search in
            pattern: Pattern to search for
            
        Returns:
            Iterator[int]: Iterator of positions where pattern was found
        """
        for i in range(len(source) - len(pattern) + 1):
            if source[i:i + len(pattern)] == pattern:
                yield i
    
    def get_port_friendly_name(self, port_name: str) -> str:
        """
        Get friendly name for a COM port
        
        Args:
            port_name: Port name to get friendly name for
            
        Returns:
            str: Friendly name of the port
        """
        if platform.system() == "Windows":
            try:
                # Use PowerShell to get port friendly name
                cmd = f'powershell "Get-WmiObject Win32_PnPEntity | Where-Object {{ $_.Name -like \'%{port_name}%\' }} | Select-Object -ExpandProperty Name"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
        return port_name
    
    def list_ports(self) -> List[Dict[str, str]]:
        """
        List available serial ports with friendly names
        
        Returns:
            List[Dict[str, str]]: List of ports with their friendly names
        """
        ports = []
        for port in serial.tools.list_ports.comports():
            friendly_name = self.get_port_friendly_name(port.device)
            ports.append({
                'device': port.device,
                'friendly_name': friendly_name,
                'description': port.description
            })
        return ports
    
    def validate_port(self, port: str) -> bool:
        """
        Validate serial port name
        
        Args:
            port: Port name to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Port should not be empty and should be in the list of available ports
        return bool(port and port in [p['device'] for p in self.list_ports()])
    
    def validate_error_code(self, error_code: str) -> bool:
        """
        Validate error code format
        
        Args:
            error_code: Error code to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Error codes should be 8 characters long and contain only hex digits
        return bool(re.match(r'^[0-9A-F]{8}$', error_code.upper()))
    
    def validate_command(self, command: str) -> bool:
        """
        Validate custom command format
        
        Args:
            command: Command to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Commands should not be empty and should not contain newlines
        return bool(command and '\n' not in command)
    
    def load_error_codes(self) -> None:
        """
        Load error codes from local database
        
        Raises:
            UartError: If database file is invalid or can't be read
        """
        try:
            if os.path.exists(self.db_path):
                tree = ET.parse(self.db_path)
                root = tree.getroot()
                if root.tag == "errorCodes":
                    for error_code in root.findall("errorCode"):
                        code = error_code.find("ErrorCode")
                        desc = error_code.find("Description")
                        if code is not None and desc is not None:
                            self.error_codes_db[code.text] = desc.text
        except ET.ParseError as e:
            raise UartError("Invalid error codes database format", str(e))
        except Exception as e:
            raise UartError("Failed to load error codes database", str(e))
    
    def save_error_codes(self) -> None:
        """
        Save error codes to local database
        
        Raises:
            UartError: If database can't be written
        """
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Create XML structure
            root = ET.Element("errorCodes")
            for code, desc in self.error_codes_db.items():
                error_code = ET.SubElement(root, "errorCode")
                ET.SubElement(error_code, "ErrorCode").text = code
                ET.SubElement(error_code, "Description").text = desc
            
            # Write to file
            tree = ET.ElementTree(root)
            tree.write(self.db_path, encoding='utf-8', xml_declaration=True)
        except IOError as e:
            raise UartError(f"Failed to write error codes database: {self.db_path}", str(e))
        except Exception as e:
            raise UartError("Failed to save error codes database", str(e))
    
    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """
        Connect to UART device
        
        Args:
            port: Serial port name
            baudrate: Baud rate (default: 115200)
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            UartError: If connection fails
        """
        if not self.validate_port(port):
            raise UartError(f"Invalid port name: {port}")
        
        try:
            self.connection = serial.Serial(port, baudrate, timeout=1)
            return True
        except serial.SerialException as e:
            raise UartError(f"Failed to connect to UART device: {port}", str(e))
        except Exception as e:
            raise UartError("Unexpected error connecting to UART device", str(e))
    
    def disconnect(self) -> None:
        """
        Disconnect from UART device
        
        Raises:
            UartError: If disconnection fails
        """
        if self.connection:
            try:
                self.connection.close()
            except serial.SerialException as e:
                raise UartError("Failed to disconnect from UART device", str(e))
            finally:
                self.connection = None
    
    def send_command(self, command: str) -> Optional[str]:
        """
        Send a command to the UART device and get response
        
        Args:
            command: Command to send
            
        Returns:
            Optional[str]: Response from device or None if failed
            
        Raises:
            UartError: If not connected or command fails
        """
        if not self.connection:
            raise UartError("Not connected to UART device")
        
        if not self.validate_command(command):
            raise UartError("Invalid command format")
        
        try:
            # Add checksum to command
            command_with_checksum = self.calculate_checksum(command)
            self.connection.write(command_with_checksum.encode() + b'\n')
            response = self.connection.readline().decode().strip()
            return self.handle_error_response(response)
        except serial.SerialException as e:
            raise UartError("Failed to send UART command", str(e))
        except Exception as e:
            raise UartError("Unexpected error sending UART command", str(e))
    
    def send_custom_command(self, command: str) -> Optional[str]:
        """
        Send a custom command to the UART device
        
        Args:
            command: Custom command to send
            
        Returns:
            Optional[str]: Response from device or None if failed
            
        Raises:
            UartError: If not connected or command fails
        """
        if not self.connection:
            raise UartError("Not connected to UART device")
        
        if not self.validate_command(command):
            raise UartError("Invalid command format")
        
        try:
            # Add checksum to command
            command_with_checksum = self.calculate_checksum(command)
            self.connection.write(command_with_checksum.encode() + b'\n')
            response = self.connection.readline().decode().strip()
            return self.handle_error_response(response)
        except serial.SerialException as e:
            raise UartError("Failed to send custom UART command", str(e))
        except Exception as e:
            raise UartError("Unexpected error sending custom UART command", str(e))
    
    def get_error_codes(self) -> List[str]:
        """
        Get error codes from PS5 system
        
        Returns:
            List[str]: List of error codes
            
        Raises:
            UartError: If not connected or command fails
        """
        if not self.connection:
            raise UartError("Not connected to UART device")
        
        try:
            response = self.send_command("get_error_codes")
            if response:
                # Parse error codes from response
                # Format: "ERROR:code1,code2,code3"
                if response.startswith("ERROR:"):
                    codes = response[6:].split(',')
                    return [code.strip() for code in codes if code.strip() and self.validate_error_code(code.strip())]
            return []
        except UartError as e:
            raise UartError("Failed to get error codes", str(e))
    
    def clear_error_codes(self) -> bool:
        """
        Clear error codes from PS5 system
        
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            UartError: If not connected or command fails
        """
        if not self.connection:
            raise UartError("Not connected to UART device")
        
        try:
            response = self.send_command("clear_error_codes")
            return response == "OK"
        except UartError as e:
            raise UartError("Failed to clear error codes", str(e))
    
    def parse_error_code(self, error_code: str, use_offline: bool = False) -> str:
        """
        Parse error code with detailed information
        
        Args:
            error_code: Error code to parse
            use_offline: Whether to use offline database
            
        Returns:
            str: Detailed error information
            
        Raises:
            UartError: If parsing fails
        """
        if not self.validate_error_code(error_code):
            raise UartError("Invalid error code format")
        
        if use_offline:
            return self._parse_error_offline(error_code)
        
        try:
            response = requests.get(f"http://uartcodes.com/xml.php?errorCode={error_code}")
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                if root.tag == "errorCodes":
                    for error_code_node in root.findall("errorCode"):
                        code = error_code_node.find("ErrorCode")
                        desc = error_code_node.find("Description")
                        if code is not None and desc is not None and code.text == error_code:
                            return f"Error code: {code.text}\nDescription: {desc.text}"
            return f"Error code: {error_code}\nNo description available"
        except Exception as e:
            raise UartError("Failed to parse error code", str(e))
    
    def _parse_error_offline(self, error_code: str) -> str:
        """
        Parse error code using offline database
        
        Args:
            error_code: Error code to parse
            
        Returns:
            str: Detailed error information
        """
        if error_code in self.error_codes_db:
            return f"Error code: {error_code}\nDescription: {self.error_codes_db[error_code]}"
        return f"Error code: {error_code}\nNo description available in offline database"
    
    def get_error_description(self, error_code: str) -> str:
        """
        Get description for an error code
        
        Args:
            error_code: Error code to look up
            
        Returns:
            str: Description of the error code
            
        Raises:
            UartError: If lookup fails
        """
        if not self.validate_error_code(error_code):
            raise UartError("Invalid error code format")
        
        if error_code in self.error_codes_db:
            return self.error_codes_db[error_code]
        
        # Try to fetch from online database
        try:
            response = requests.get(f"http://uartcodes.com/xml.php?errorCode={error_code}")
            if response.status_code == 200:
                # Parse XML response
                root = ET.fromstring(response.text)
                if root.tag == "errorCodes":
                    for error_code_node in root.findall("errorCode"):
                        code = error_code_node.find("ErrorCode")
                        desc = error_code_node.find("Description")
                        if code is not None and desc is not None and code.text == error_code:
                            self.error_codes_db[error_code] = desc.text
                            self.save_error_codes()
                            return desc.text
        except requests.RequestException as e:
            raise UartError("Failed to fetch error description from online database", str(e))
        except ET.ParseError as e:
            raise UartError("Failed to parse error description response", str(e))
        except Exception as e:
            raise UartError("Unexpected error getting error description", str(e))
        
        return "Unknown error"
    
    def download_error_database(self) -> bool:
        """
        Download complete error code database
        
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            UartError: If download fails
        """
        try:
            response = requests.get("http://uartcodes.com/xml.php")
            if response.status_code == 200:
                # Parse XML response
                root = ET.fromstring(response.text)
                if root.tag == "errorCodes":
                    self.error_codes_db.clear()
                    for error_code in root.findall("errorCode"):
                        code = error_code.find("ErrorCode")
                        desc = error_code.find("Description")
                        if code is not None and desc is not None and self.validate_error_code(code.text):
                            self.error_codes_db[code.text] = desc.text
                    self.save_error_codes()
                    return True
            return False
        except requests.RequestException as e:
            raise UartError("Failed to download error database", str(e))
        except ET.ParseError as e:
            raise UartError("Failed to parse error database response", str(e))
        except Exception as e:
            raise UartError("Unexpected error downloading error database", str(e))
    
    def detect_console_version(self, nor_data: bytes) -> str:
        """
        Detect PS5 console version from NOR data
        
        Args:
            nor_data: NOR file data
            
        Returns:
            str: Console version information
            
        Raises:
            UartError: If detection fails
        """
        try:
            if not self.validate_nor_file(nor_data):
                raise UartError("Invalid NOR file")
                
            offset_one_value = nor_data[OFFSET_ONE:OFFSET_ONE + 16].decode('ascii').strip('\x00')
            offset_two_value = nor_data[OFFSET_TWO:OFFSET_TWO + 16].decode('ascii').strip('\x00')
            
            if offset_one_value and offset_two_value:
                return f"Console Version: {offset_one_value}\nVariant: {offset_two_value}"
            return "Console version not detected"
        except Exception as e:
            raise UartError("Failed to detect console version", str(e))
    
    def convert_to_digital_edition(self, nor_data: bytes) -> bytes:
        """
        Convert PS5 to digital edition by modifying NOR data
        
        Args:
            nor_data: Original NOR file data
            
        Returns:
            bytes: Modified NOR data for digital edition
            
        Raises:
            UartError: If conversion fails
        """
        try:
            if not self.validate_nor_file(nor_data):
                raise UartError("Invalid NOR file")
                
            # Create a copy of the NOR data
            modified_data = bytearray(nor_data)
            
            # Modify the variant value at the variant offset
            variant_value = "DIGITAL"
            modified_data[VARIANT_OFFSET:VARIANT_OFFSET + len(variant_value)] = variant_value.encode('ascii')
            
            return bytes(modified_data)
        except Exception as e:
            raise UartError("Failed to convert to digital edition", str(e))
    
    def get_mac_addresses(self, nor_data: bytes) -> Dict[str, str]:
        """
        Get WiFi and LAN MAC addresses from NOR data
        
        Args:
            nor_data: NOR file data
            
        Returns:
            Dict[str, str]: Dictionary containing WiFi and LAN MAC addresses
            
        Raises:
            UartError: If MAC address extraction fails
        """
        try:
            if not self.validate_nor_file(nor_data):
                raise UartError("Invalid NOR file")
                
            wifi_mac = nor_data[WIFI_MAC_OFFSET:WIFI_MAC_OFFSET + 12].hex().upper()
            lan_mac = nor_data[LAN_MAC_OFFSET:LAN_MAC_OFFSET + 12].hex().upper()
            
            # Format MAC addresses with colons
            wifi_mac = ':'.join(wifi_mac[i:i+2] for i in range(0, len(wifi_mac), 2))
            lan_mac = ':'.join(lan_mac[i:i+2] for i in range(0, len(lan_mac), 2))
            
            return {
                'wifi': wifi_mac,
                'lan': lan_mac
            }
        except Exception as e:
            raise UartError("Failed to extract MAC addresses", str(e))
    
    def get_serial_numbers(self, nor_data: bytes) -> Dict[str, str]:
        """
        Get console and motherboard serial numbers from NOR data
        
        Args:
            nor_data: NOR file data
            
        Returns:
            Dict[str, str]: Dictionary containing console and motherboard serial numbers
            
        Raises:
            UartError: If serial number extraction fails
        """
        try:
            if not self.validate_nor_file(nor_data):
                raise UartError("Invalid NOR file")
                
            console_serial = nor_data[SERIAL_OFFSET:SERIAL_OFFSET + 10].decode('ascii').strip('\x00')
            mobo_serial = nor_data[MOBO_SERIAL_OFFSET:MOBO_SERIAL_OFFSET + 10].decode('ascii').strip('\x00')
            
            return {
                'console': console_serial,
                'motherboard': mobo_serial
            }
        except Exception as e:
            raise UartError("Failed to extract serial numbers", str(e))
    
    def open_url(self, url: str) -> None:
        """
        Open a URL in the default web browser
        
        Args:
            url: URL to open
            
        Raises:
            UartError: If URL is invalid or can't be opened
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise UartError("Invalid URL")
            
            # Open URL in default browser
            webbrowser.open(url)
        except Exception as e:
            raise UartError("Failed to open URL", str(e))
    
    def download_file(self, url: str, save_path: str) -> bool:
        """
        Download a file from a URL
        
        Args:
            url: URL to download from
            save_path: Path to save the file to
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            UartError: If download fails
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise UartError("Invalid URL")
            
            # Download file
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Save file
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except requests.RequestException as e:
            raise UartError("Failed to download file", str(e))
        except IOError as e:
            raise UartError(f"Failed to save file: {save_path}", str(e))
        except Exception as e:
            raise UartError("Unexpected error downloading file", str(e)) 