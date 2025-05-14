from typing import Optional, Union, List, Tuple
from dataclasses import dataclass
import os

@dataclass
class NorError(Exception):
    """Custom exception for NOR file operations"""
    message: str
    details: Optional[str] = None

class NorHandler:
    def __init__(self):
        self.nor_data: Optional[bytearray] = None
        
        # NOR file offsets
        self.OFFSET_ONE: int = 0x1c7010
        self.OFFSET_TWO: int = 0x1c7030
        self.WIFI_MAC_OFFSET: int = 0x1C73C0
        self.LAN_MAC_OFFSET: int = 0x1C4020
        self.SERIAL_OFFSET: int = 0x1c7210
        self.VARIANT_OFFSET: int = 0x1c7226
        self.MOBO_SERIAL_OFFSET: int = 0x1C7200
        
        # Constants
        self.SERIAL_LENGTH: int = 16
        self.MAC_LENGTH: int = 6
    
    def load_nor_file(self, file_path: str) -> bool:
        """
        Load a NOR file into memory
        
        Args:
            file_path: Path to the NOR file
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            NorError: If file doesn't exist or can't be read
        """
        try:
            if not os.path.exists(file_path):
                raise NorError(f"NOR file not found: {file_path}")
            
            with open(file_path, 'rb') as f:
                self.nor_data = bytearray(f.read())
            
            if not self.nor_data:
                raise NorError("Loaded NOR file is empty")
            
            return True
            
        except IOError as e:
            raise NorError(f"Failed to read NOR file: {file_path}", str(e))
        except Exception as e:
            raise NorError("Unexpected error loading NOR file", str(e))
    
    def save_nor_file(self, file_path: str) -> bool:
        """
        Save the current NOR data to a file
        
        Args:
            file_path: Path to save the NOR file
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            NorError: If no data to save or can't write file
        """
        if not self.nor_data:
            raise NorError("No NOR data to save")
        
        try:
            with open(file_path, 'wb') as f:
                f.write(self.nor_data)
            return True
            
        except IOError as e:
            raise NorError(f"Failed to write NOR file: {file_path}", str(e))
        except Exception as e:
            raise NorError("Unexpected error saving NOR file", str(e))
    
    def _read_string(self, offset: int, length: int) -> Optional[str]:
        """
        Read a string from the NOR data at the specified offset
        
        Args:
            offset: Byte offset in the NOR data
            length: Length of string to read
            
        Returns:
            Optional[str]: The read string or None if invalid
            
        Raises:
            NorError: If offset or length is invalid
        """
        try:
            if not self.nor_data:
                raise NorError("No NOR data loaded")
            
            if offset < 0 or offset + length > len(self.nor_data):
                raise NorError(f"Invalid offset {offset} or length {length}")
            
            return self.nor_data[offset:offset + length].decode('ascii', errors='ignore').strip('\x00')
            
        except UnicodeDecodeError as e:
            raise NorError(f"Failed to decode string at offset {offset}", str(e))
        except Exception as e:
            raise NorError("Unexpected error reading string", str(e))
    
    def _write_string(self, offset: int, value: str, length: int) -> bool:
        """
        Write a string to the NOR data at the specified offset
        
        Args:
            offset: Byte offset in the NOR data
            value: String to write
            length: Length of string to write
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            NorError: If offset or length is invalid
        """
        try:
            if not self.nor_data:
                raise NorError("No NOR data loaded")
            
            if offset < 0 or offset + length > len(self.nor_data):
                raise NorError(f"Invalid offset {offset} or length {length}")
            
            # Convert string to bytes and pad with nulls
            value_bytes = value.encode('ascii')
            if len(value_bytes) > length:
                raise NorError(f"String too long: {len(value_bytes)} > {length}")
            
            padded_bytes = value_bytes.ljust(length, b'\x00')
            
            # Write to NOR data
            self.nor_data[offset:offset + length] = padded_bytes
            return True
            
        except UnicodeEncodeError as e:
            raise NorError(f"Failed to encode string: {value}", str(e))
        except Exception as e:
            raise NorError("Unexpected error writing string", str(e))
    
    def get_serial_number(self) -> Optional[str]:
        """
        Extract the serial number from the NOR data
        
        Returns:
            Optional[str]: The serial number or None if not found
            
        Raises:
            NorError: If NOR data is not loaded
        """
        try:
            return self._read_string(self.SERIAL_OFFSET, self.SERIAL_LENGTH)
        except NorError as e:
            raise NorError("Failed to read serial number", str(e))
    
    def set_serial_number(self, new_serial: str) -> bool:
        """
        Set a new serial number in the NOR data
        
        Args:
            new_serial: New serial number to set
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            NorError: If serial number is invalid
        """
        try:
            if len(new_serial) != self.SERIAL_LENGTH:
                raise NorError(f"Invalid serial number length: {len(new_serial)} != {self.SERIAL_LENGTH}")
            
            return self._write_string(self.SERIAL_OFFSET, new_serial, self.SERIAL_LENGTH)
            
        except NorError as e:
            raise NorError("Failed to set serial number", str(e))
    
    def get_version(self) -> Optional[str]:
        """
        Get the current version (Disc/Digital)
        
        Returns:
            Optional[str]: "Disc Edition", "Digital Edition", or None
            
        Raises:
            NorError: If version flags are invalid
        """
        try:
            offset_one_value = self._read_string(self.OFFSET_ONE, 1)
            offset_two_value = self._read_string(self.OFFSET_TWO, 1)
            
            if offset_one_value == "1" and offset_two_value == "1":
                return "Disc Edition"
            elif offset_one_value == "0" and offset_two_value == "0":
                return "Digital Edition"
            return "Unknown"
            
        except NorError as e:
            raise NorError("Failed to read version", str(e))
    
    def set_version(self, is_disc_edition: bool) -> bool:
        """
        Set the version flags (Disc/Digital)
        
        Args:
            is_disc_edition: True for Disc Edition, False for Digital Edition
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            NorError: If version flags can't be set
        """
        try:
            value = "1" if is_disc_edition else "0"
            success = self._write_string(self.OFFSET_ONE, value, 1)
            success &= self._write_string(self.OFFSET_TWO, value, 1)
            return success
            
        except NorError as e:
            raise NorError("Failed to set version", str(e))
    
    def get_motherboard_serial(self) -> Optional[str]:
        """
        Get the motherboard serial number
        
        Returns:
            Optional[str]: The motherboard serial number or None if not found
            
        Raises:
            NorError: If NOR data is not loaded
        """
        try:
            return self._read_string(self.MOBO_SERIAL_OFFSET, self.SERIAL_LENGTH)
        except NorError as e:
            raise NorError("Failed to read motherboard serial", str(e))
    
    def get_wifi_mac(self) -> Optional[str]:
        """
        Get the WiFi MAC address
        
        Returns:
            Optional[str]: The WiFi MAC address in format "XX:XX:XX:XX:XX:XX" or None if not found
            
        Raises:
            NorError: If NOR data is not loaded
        """
        try:
            if not self.nor_data:
                raise NorError("No NOR data loaded")
            
            mac_bytes = self.nor_data[self.WIFI_MAC_OFFSET:self.WIFI_MAC_OFFSET + self.MAC_LENGTH]
            return ':'.join(f'{b:02x}' for b in mac_bytes)
            
        except Exception as e:
            raise NorError("Failed to read WiFi MAC", str(e))
    
    def get_lan_mac(self) -> Optional[str]:
        """
        Get the LAN MAC address
        
        Returns:
            Optional[str]: The LAN MAC address in format "XX:XX:XX:XX:XX:XX" or None if not found
            
        Raises:
            NorError: If NOR data is not loaded
        """
        try:
            if not self.nor_data:
                raise NorError("No NOR data loaded")
            
            mac_bytes = self.nor_data[self.LAN_MAC_OFFSET:self.LAN_MAC_OFFSET + self.MAC_LENGTH]
            return ':'.join(f'{b:02x}' for b in mac_bytes)
            
        except Exception as e:
            raise NorError("Failed to read LAN MAC", str(e)) 