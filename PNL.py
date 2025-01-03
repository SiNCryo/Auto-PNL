import tkinter as tk
from flask import Flask, jsonify, render_template_string, request
import threading
import requests
import os
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

# Flask app setup
app = Flask(__name__)

# Initial data for balance and PNL
data = {"balance": 0.0, "pnl": 0.0}
wallet_address = None

# Solana RPC Endpoint
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# HTML template for the overlay
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Overlay</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@300&display=swap');
        body {
            font-family: 'Cinzel', serif;
            background: rgba(255, 255, 255, 0.02); /* Very light transparent tint */
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .overlay {
            background: rgba(255, 255, 255, 0.02); /* More transparent tint */
            padding: 10px;
            border-radius: 10px; /* Rounded corners */
            text-align: center;
            display: inline-block;
        }
        .title {
            font-size: 14px; /* Smaller title font */
            font-weight: 300; /* Lighter font */
            margin: 0 15px; /* Spacing between titles */
            display: inline-block;
        }
        .balance-number, .pnl-number {
            font-size: 20px; /* Bigger numbers */
            font-weight: bold;
            margin-top: 5px;
        }
        .pnl-title, .pnl-number {
            color: #32CD32; /* Brighter lime green */
        }
        .logo {
            height: 14px; /* Smaller logo */
            vertical-align: middle;
        }
    </style>
</head>
<body>
    <div class="overlay">
        <div class="title">BALANCE:<br><span class="balance-number">{{ balance }} <span class="logo">◎</span></span></div>
        <div class="title pnl-title">PNL:<br><span class="pnl-number">{{ pnl }} <span class="logo">◎</span></span></div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, balance=data["balance"], pnl=data["pnl"])

@app.route("/update", methods=["POST"])
def update():
    global data
    transaction = request.json
    amount = transaction["amount"]
    action = transaction["action"]

    if action == "spend":
        data["balance"] -= amount
    elif action == "sell":
        data["balance"] += amount
        data["pnl"] += amount

    return jsonify(success=True)

def fetch_balance():
    global wallet_address
    if wallet_address:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [wallet_address]
        }
        try:
            response = requests.post(SOLANA_RPC_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            data["balance"] = result.get("result", {}).get("value", 0) / 1e9  # Convert lamports to SOL
        except Exception as e:
            print(f"Error fetching balance from Solana API: {e}")

# Flask server thread
def run_flask(server_ready_event):
    try:
        fetch_balance()  # Fetch initial balance
        server_ready_event.set()  # Notify Flask is ready
        app.run(debug=False, host="127.0.0.1", port=5000)
    except Exception as e:
        print(f"Error starting Flask server: {e}")

# System tray integration
def setup_tray():
    def quit_app(icon, item):
        icon.stop()
        os._exit(0)  # Fully terminate the program

    # Create a small icon for the tray
    icon_image = Image.new("RGB", (64, 64), (0, 0, 0))
    draw = ImageDraw.Draw(icon_image)
    draw.rectangle((16, 16, 48, 48), fill="lime")

    menu = Menu(MenuItem("Exit", quit_app))
    icon = Icon("Crypto Overlay", icon_image, menu=menu)
    icon.run()

# GUI pop-up to get the wallet address
def get_wallet_address():
    global wallet_address

    root = tk.Tk()
    root.withdraw()  # Hide the main Tkinter window

    # Create a custom pop-up dialog
    popup = tk.Toplevel()
    popup.title("Enter Wallet Address")
    popup.configure(bg="black")

    tk.Label(popup, text="Enter your Solana wallet address:", fg="green", bg="black", font=("Cinzel", 12)).pack(pady=10)
    wallet_entry = tk.Entry(popup, width=50, font=("Cinzel", 12))
    wallet_entry.pack(pady=10)
    wallet_entry.bind("<Button-3>", lambda e: wallet_entry.event_generate("<<Paste>>"))  # Enable right-click paste

    def confirm():
        global wallet_address
        wallet_address = wallet_entry.get()
        if wallet_address:
            popup.destroy()  # Close the pop-up

            # Start Flask server in a thread
            server_ready_event = threading.Event()
            threading.Thread(target=run_flask, args=(server_ready_event,), daemon=True).start()
            server_ready_event.wait()  # Wait until Flask is ready

            # Start system tray in a separate thread
            threading.Thread(target=setup_tray, daemon=True).start()
        else:
            os._exit(0)  # Exit if no address is entered

    def on_close():
        os._exit(0)  # Exit without error

    popup.protocol("WM_DELETE_WINDOW", on_close)  # Handle close button

    tk.Button(popup, text="Confirm", command=confirm, fg="black", bg="limegreen", font=("Cinzel", 12)).pack(pady=10)

    # Instructions
    instructions = [
        "1. Enter your Solana wallet address and click 'Confirm'.",
        "2. The app will minimize to the system tray after confirming.",
        "3. Open OBS Studio.",
        "4. Add a 'Browser Source' in OBS.",
        "5. Enter the following URL: http://127.0.0.1:5000/",
        "6. Adjust the size and placement of the overlay in OBS.",
        "7. To exit the program, right-click the system tray icon and select 'Exit'."
    ]
    for step in instructions:
        tk.Label(popup, text=step, fg="limegreen", bg="black", font=("Cinzel", 10), wraplength=400, justify="left").pack(anchor="w", padx=20)

    root.mainloop()

if __name__ == "__main__":
    get_wallet_address()
