import asyncio
import sys
from bleak import BleakScanner

# Common Service UUID for ELK-BLEDOM / Lotus Lantern / Triones strips
TARGET_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"

async def run():
    print("==========================================")
    print("       LED STRIP MAC ADDRESS FINDER       ")
    print("==========================================")
    print("Searching for compatible devices... (10s)")
    print("Ensure your LED strip is powered ON and nearby.\n")

    try:
        # Scan for 10 seconds
        devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    except Exception as e:
        print(f"❌ Error during scan: {e}")
        return

    found_count = 0
    for addr, (device, adv) in devices.items():
        name = device.name or "Unknown Device"
        uuids = [u.lower() for u in adv.service_uuids]

        # Criteria for ELK-BLEDOM protocol compatibility:
        # 1. Known name patterns
        # 2. Presence of the FFF0 service UUID
        is_compatible = (
            any(x in name.upper() for x in ["ELK", "BLEDOM", "TRIONES", "GESTO", "LED", "CLK"]) or
            TARGET_SERVICE_UUID.lower() in uuids
        )

        if is_compatible:
            found_count += 1
            print(f"✅ Found Compatible Device:")
            print(f"   Name:    {name}")
            print(f"   Address: {device.address}  <-- COPY THIS")
            print(f"   RSSI:    {adv.rssi} dBm")
            if adv.service_uuids:
                print(f"   UUIDs:   {adv.service_uuids}")
            print("-" * 42)

    if found_count == 0:
        print("❌ No compatible LED strips found.")
        print("Try moving closer or restarting the LED strip's power.")
    else:
        print(f"\nDone! Found {found_count} potential device(s).")
        print("Copy the Address above and paste it into your config.py")

    input("\nPress Enter to exit...")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)