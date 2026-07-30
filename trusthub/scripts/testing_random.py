from pathlib import Path

folders = [
    r"C:\trusthub\AES_unzipped\RS232-T1000\RS232-T1000\src\90nm",
    r"C:\trusthub\AES_unzipped\RS232-T2100\RS232-T2100\src\TjIn"
]

for folder in folders:
    print("\n", folder)
    p = Path(folder)

    for f in sorted(p.glob("*")):
        print("   ", f.name)