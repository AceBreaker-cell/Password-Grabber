#!/usr/bin/env python3
"""
WiFi Password Grabber for Windows and Linux
Allows user to select OS and then retrieves saved WiFi passwords.
"""

import subprocess
import sys
import os
import re

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def save_to_csv(results, filename=None):
    """Save results to a CSV file."""
    import csv
    from datetime import datetime

    if not results:
        print("No data to save.")
        return False

    if filename is None:
        # Generate a filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"wifi_passwords_{timestamp}.csv"

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['SSID', 'Password']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for result in results:
                writer.writerow(result)

        print(f"Results saved to {filename}")
        return True
    except Exception as e:
        print(f"Error saving to CSV: {e}")
        return False

def is_windows():
    return os.name == 'nt'

def is_linux():
    return sys.platform.startswith('linux')

def get_wifi_passwords_windows():
    """Retrieve WiFi passwords on Windows using netsh."""
    try:
        # Get all profiles
        output = subprocess.check_output(['netsh', 'wlan', 'show', 'profiles'],
                                         stderr=subprocess.STDOUT,
                                         universal_newlines=True)
        # Extract profile names
        profiles = re.findall(r"All User Profile\s+:\s(.*)", output)

        if not profiles:
            print("No WiFi profiles found.")
            return []

        results = []
        print(f"{'SSID':<30} {'Password'}")
        print("-" * 50)
        for profile in profiles:
            profile = profile.strip()
            try:
                # Get detailed info including password
                details = subprocess.check_output(['netsh', 'wlan', 'show', 'profile', f'name={profile}', 'key=clear'],
                                                  stderr=subprocess.STDOUT,
                                                  universal_newlines=True)
                # Extract password
                password_match = re.search(r"Key Content\s+:\s(.*)", details)
                password = password_match.group(1) if password_match else ""
                if not password:
                    password = ""  # If no password (open network)
                print(f"{profile:<30} {password}")
                results.append({"SSID": profile, "Password": password})
            except subprocess.CalledProcessError as e:
                print(f"{profile:<30} Error retrieving password: {e.output.strip()}")
                results.append({"SSID": profile, "Password": f"Error: {e.output.strip()}"})
            except Exception as e:
                print(f"{profile:<30} Unexpected error: {e}")
                results.append({"SSID": profile, "Password": f"Error: {e}"})
        return results
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving WiFi profiles: {e.output}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []

def get_wifi_passwords_linux():
    """Retrieve WiFi passwords on Linux using NetworkManager or nmcli."""
    # Try nmcli first if available
    if subprocess.run(['which', 'nmcli'], capture_output=True).returncode == 0:
        return get_wifi_passwords_linux_nmcli()
    else:
        return get_wifi_passwords_linux_files()

def get_wifi_passwords_linux_nmcli():
    """Use nmcli to show WiFi passwords (requires sudo)."""
    try:
        # Check if we have sudo privileges by trying to run nmcli with sudo
        # We'll run a test command to see if we can get connections without password
        test = subprocess.run(['sudo', '-n', 'nmcli', '-t', '-f', 'NAME,UUID', 'connection', 'show'],
                              capture_output=True, text=True)
        if test.returncode != 0:
            # If sudo fails, ask for password
            print("This operation requires sudo privileges.")
            # We'll let the actual command prompt for password
        # Get all connections
        output = subprocess.check_output(['sudo', 'nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
                                         stderr=subprocess.STDOUT,
                                         universal_newlines=True)
        # Filter for wifi connections (type 802-11-wireless)
        wifi_connections = []
        for line in output.strip().split('\n'):
            if line:
                parts = line.split(':')
                if len(parts) >= 2 and parts[1] == '802-11-wireless':
                    wifi_connections.append(parts[0])

        if not wifi_connections:
            print("No WiFi connections found.")
            return []

        results = []
        print(f"{'SSID':<30} {'Password'}")
        print("-" * 50)
        for ssid in wifi_connections:
            # Try to get the password for this connection
            try:
                # We need to show the connection details, including the wifi-sec.psk
                # The password might be in the wifi-sec section
                details_output = subprocess.check_output(['sudo', 'nmcli', '-s', '-f', '802-11-wireless-security.psk', 'connection', 'show', ssid],
                                                         stderr=subprocess.STDOUT,
                                                         universal_newlines=True)
                password = details_output.strip()
                # If the field is empty, it might be stored differently or not present
                if not password:
                    # Try to get all settings and look for the password
                    all_output = subprocess.check_output(['sudo', 'nmcli', '-s', 'connection', 'show', ssid],
                                                         stderr=subprocess.STDOUT,
                                                         universal_newlines=True)
                    # Search for psk or password in the output
                    # This is a fallback; we can parse for lines containing 'psk' or 'password'
                    # For simplicity, we'll just note that we couldn't retrieve via this method
                    password = "(Could not retrieve automatically)"
                print(f"{ssid:<30} {password}")
                results.append({"SSID": ssid, "Password": password})
            except subprocess.CalledProcessError as e:
                print(f"{ssid:<30} Error retrieving password: {e.output.strip()}")
                results.append({"SSID": ssid, "Password": f"Error: {e.output.strip()}"})
            except Exception as e:
                print(f"{ssid:<30} Unexpected error: {e}")
                results.append({"SSID": ssid, "Password": f"Error: {e}"})
        return results
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving WiFi connections: {e.output}")
        print("Tip: Make sure you have sudo privileges and nmcli is installed.")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []

def get_wifi_passwords_linux_files():
    """Read WiFi passwords from NetworkManager configuration files."""
    # Possible locations for NetworkManager connection files
    possible_paths = [
        '/etc/NetworkManager/system-connections/',
        '/var/run/NetworkManager/system-connections/',
        '/etc/NetworkManager/system-connections'  # older versions might be files without .nmconnection extension
    ]

    connections_found = []
    for path in possible_paths:
        if os.path.isdir(path):
            for filename in os.listdir(path):
                if filename.endswith('.nmconnection') or not '.' in filename:  # also consider files without extension
                    full_path = os.path.join(path, filename)
                    if os.path.isfile(full_path):
                        connections_found.append(full_path)
        elif os.path.isfile(path):
            # In case the path is a file (older format)
            connections_found.append(path)

    if not connections_found:
        print("No WiFi connection files found in typical NetworkManager directories.")
        print("You may need to run this script with sudo or check your distribution's NetworkManager configuration location.")
        return []

    results = []
    print(f"{'SSID':<30} {'Password'}")
    print("-" * 50)
    for filepath in connections_found:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            # Extract SSID (from [connection] section id=)
            ssid_match = re.search(r'^id=(.*)$', content, re.MULTILINE)
            ssid = ssid_match.group(1).strip() if ssid_match else os.path.basename(filepath)
            # Extract password from [wifi-security] or [802-11-wireless-security] section psk=
            # Some versions use different section names
            password_match = re.search(r'^\s*(?:wifi-security|802-11-wireless-security)\s*\n(?:.*\n)*?^\s*psk=(.*)$',
                                       content, re.MULTILINE)
            if not password_match:
                # Try alternative section names
                password_match = re.search(r'^\s*psk=(.*)$', content, re.MULTILINE)
            password = password_match.group(1).strip() if password_match else ""
            # If the password is stored as encrypted (e.g., with key management), we might see a different field
            # For simplicity, we just show what we find.
            print(f"{ssid:<30} {password if password else '(No password found or encrypted)'}")
            results.append({"SSID": ssid, "Password": password if password else "(No password found or encrypted)"})
        except Exception as e:
            print(f"{os.path.basename(filepath):<30} Error reading file: {e}")
            results.append({"SSID": os.path.basename(filepath), "Password": f"Error: {e}"})
    return results

def main():
    clear_screen()
    print("Albatany has ideas lol.")
    print("Select your operating system:")
    print("1. Windows")
    print("2. Linux")
    print("3. Exit")

    while True:
        choice = input("\nEnter your choice (1-3): ").strip()
        if choice == '1':
            if not is_windows():
                print("Warning: You selected Windows but are running on a non-Windows system.")
                cont = input("Continue anyway? (y/n): ").lower()
                if cont != 'y':
                    continue
            results = get_wifi_passwords_windows()
            if results:
                save_choice = input("\nDo you want to save the results to a CSV file? (y/n): ").lower()
                if save_choice == 'y':
                    save_to_csv(results)
            break
        elif choice == '2':
            if not is_linux():
                print("Warning: You selected Linux but are running on a non-Linux system.")
                cont = input("Continue anyway? (y/n): ").lower()
                if cont != 'y':
                    continue
            results = get_wifi_passwords_linux()
            if results:
                save_choice = input("\nDo you want to save the results to a CSV file? (y/n): ").lower()
                if save_choice == 'y':
                    save_to_csv(results)
            break
        elif choice == '3':
            print("Exiting...")
            sys.exit(0)
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)