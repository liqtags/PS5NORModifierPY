import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from typing import Optional, List, Dict, Union
from nor_handler import NorHandler
from uart_handler import UartHandler

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PS5 NOR Modifier")
        self.root.geometry("800x600")
        
        # Initialize handlers
        self.nor_handler = NorHandler()
        self.uart_handler = UartHandler()
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create widgets
        self._create_widgets()
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        # Set up error handling
        self.root.report_callback_exception = self._handle_exception
    
    def _create_widgets(self):
        # File operations group
        file_frame = ttk.LabelFrame(self.main_frame, text="File Operations", padding="5")
        file_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Button(file_frame, text="Load NOR File", command=self._load_nor_file).grid(row=0, column=0, padx=5)
        ttk.Button(file_frame, text="Save NOR File", command=self._save_nor_file).grid(row=0, column=1, padx=5)
        
        # Serial number group
        serial_frame = ttk.LabelFrame(self.main_frame, text="Serial Number", padding="5")
        serial_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(serial_frame, text="Current:").grid(row=0, column=0, padx=5)
        self.serial_label = ttk.Label(serial_frame, text="Not loaded")
        self.serial_label.grid(row=0, column=1, padx=5)
        
        ttk.Label(serial_frame, text="New:").grid(row=1, column=0, padx=5)
        self.serial_entry = ttk.Entry(serial_frame)
        self.serial_entry.grid(row=1, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(serial_frame, text="Update", command=self._update_serial).grid(row=1, column=2, padx=5)
        
        # MAC address group
        mac_frame = ttk.LabelFrame(self.main_frame, text="MAC Address", padding="5")
        mac_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(mac_frame, text="Current:").grid(row=0, column=0, padx=5)
        self.mac_label = ttk.Label(mac_frame, text="Not loaded")
        self.mac_label.grid(row=0, column=1, padx=5)
        
        ttk.Label(mac_frame, text="New:").grid(row=1, column=0, padx=5)
        self.mac_entry = ttk.Entry(mac_frame)
        self.mac_entry.grid(row=1, column=1, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(mac_frame, text="Update", command=self._update_mac).grid(row=1, column=2, padx=5)
        
        # UART operations group
        uart_frame = ttk.LabelFrame(self.main_frame, text="UART Operations", padding="5")
        uart_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(uart_frame, text="Port:").grid(row=0, column=0, padx=5)
        self.port_entry = ttk.Entry(uart_frame)
        self.port_entry.grid(row=0, column=1, padx=5, sticky=(tk.W, tk.E))
        
        ttk.Button(uart_frame, text="Connect", command=self._connect_uart).grid(row=0, column=2, padx=5)
        ttk.Button(uart_frame, text="Disconnect", command=self._disconnect_uart).grid(row=0, column=3, padx=5)
        
        # Error codes list
        error_frame = ttk.LabelFrame(self.main_frame, text="Error Codes", padding="5")
        error_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.error_list = tk.Listbox(error_frame, height=10)
        self.error_list.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(error_frame, orient=tk.VERTICAL, command=self.error_list.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.error_list.configure(yscrollcommand=scrollbar.set)
        
        ttk.Button(error_frame, text="Get Error Codes", command=self._get_error_codes).grid(row=1, column=0, pady=5)
        ttk.Button(error_frame, text="Clear Error Codes", command=self._clear_error_codes).grid(row=1, column=1, pady=5)
        
        # Configure grid weights for error frame
        error_frame.columnconfigure(0, weight=1)
        error_frame.rowconfigure(0, weight=1)
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions"""
        messagebox.showerror("Error", str(exc_value))
    
    def _load_nor_file(self):
        """Load a NOR file"""
        try:
            filename = filedialog.askopenfilename(
                title="Select NOR File",
                filetypes=[("NOR files", "*.nor"), ("All files", "*.*")]
            )
            if filename:
                if self.nor_handler.load_nor_file(filename):
                    self._update_ui()
                    messagebox.showinfo("Success", "NOR file loaded successfully")
                else:
                    messagebox.showerror("Error", "Failed to load NOR file")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _save_nor_file(self):
        """Save the current NOR file"""
        try:
            filename = filedialog.asksaveasfilename(
                title="Save NOR File",
                defaultextension=".nor",
                filetypes=[("NOR files", "*.nor"), ("All files", "*.*")]
            )
            if filename:
                if self.nor_handler.save_nor_file(filename):
                    messagebox.showinfo("Success", "NOR file saved successfully")
                else:
                    messagebox.showerror("Error", "Failed to save NOR file")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _update_ui(self):
        """Update UI elements with current values"""
        try:
            serial = self.nor_handler.get_serial_number()
            mac = self.nor_handler.get_mac_address()
            
            self.serial_label.config(text=serial if serial else "Not loaded")
            self.mac_label.config(text=mac if mac else "Not loaded")
            
            self.serial_entry.delete(0, tk.END)
            self.mac_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _update_serial(self):
        """Update serial number"""
        try:
            new_serial = self.serial_entry.get().strip()
            if self.nor_handler.set_serial_number(new_serial):
                self._update_ui()
                messagebox.showinfo("Success", "Serial number updated successfully")
            else:
                messagebox.showerror("Error", "Failed to update serial number")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _update_mac(self):
        """Update MAC address"""
        try:
            new_mac = self.mac_entry.get().strip()
            if self.nor_handler.set_mac_address(new_mac):
                self._update_ui()
                messagebox.showinfo("Success", "MAC address updated successfully")
            else:
                messagebox.showerror("Error", "Failed to update MAC address")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _connect_uart(self):
        """Connect to UART device"""
        try:
            port = self.port_entry.get().strip()
            if self.uart_handler.connect(port):
                messagebox.showinfo("Success", "Connected to UART device")
            else:
                messagebox.showerror("Error", "Failed to connect to UART device")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _disconnect_uart(self):
        """Disconnect from UART device"""
        try:
            self.uart_handler.disconnect()
            messagebox.showinfo("Success", "Disconnected from UART device")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _get_error_codes(self):
        """Get error codes from PS5"""
        try:
            error_codes = self.uart_handler.get_error_codes()
            self.error_list.delete(0, tk.END)
            for code in error_codes:
                desc = self.uart_handler.get_error_description(code)
                self.error_list.insert(tk.END, f"{code}: {desc}")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _clear_error_codes(self):
        """Clear error codes from PS5"""
        try:
            if self.uart_handler.clear_error_codes():
                self.error_list.delete(0, tk.END)
                messagebox.showinfo("Success", "Error codes cleared successfully")
            else:
                messagebox.showerror("Error", "Failed to clear error codes")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def run(self):
        """Start the application"""
        self.root.mainloop() 