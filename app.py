
from flask import Flask, request, redirect, render_template
import pymysql
import struct
import os

#- Default Environment -----------------------------------------------------------------------------

app = Flask(__name__)
CONFIG_FILE = "config.bin"

# Default config (if file doesn't exist)
DEFAULT_VALUES = {
    "ECGRateEvenValue" : [0, 255, 0],
    "ECGRateThreeValue": [0, 0, 255],
    "ECGRateElseValue" : [255, 255, 255],
    "ECGRateDisconnectedThreshhold": [255, 0, 0],
    "MotionSensitiveThreshold": 1000,
    "TemperatureThreshhold": 10
}

DB_CONFIG = {
    "host": "localhost",
    "user": "edge",
    "password": "",
    "database": "swe30011"
}


#- Helper Functions --------------------------------------------------------------------------------

def clamp( aValue, aMin, aMax ):
    return max( aMin, min( aMax, aValue ))


def load_binary_config():
    if not os.path.exists( CONFIG_FILE ):
        return DEFAULT_VALUES.copy()

    with open( CONFIG_FILE, "rb" ) as lFile:
        lData = lFile.read()

    lUnpacked = struct.unpack( "<BBBBBBBBBBBBhh", lData )  # 12 bytes + 2 int16_t

    return {
        "ECGRateEvenValue": list( lUnpacked[0:3] ),
        "ECGRateThreeValue": list( lUnpacked[3:6] ),
        "ECGRateElseValue": list( lUnpacked[6:9] ),
        "ECGRateDisconnectedThreshhold": list( lUnpacked[9:12] ),
        "MotionSensitiveThreshold": lUnpacked[12],
        "TemperatureThreshhold": lUnpacked[13]
    }


def save_binary_config( aData ):
    # Clamp and sanitise values
    for lKey in [
        "ECGRateEvenValue", "ECGRateThreeValue", "ECGRateElseValue", "ECGRateDisconnectedThreshhold"
    ]:
        aData[lKey] = [clamp( int(lValue), 0, 255 ) for lValue in aData[lKey]]

    aData["MotionSensitiveThreshold"] = clamp(
        int( aData["MotionSensitiveThreshold"] ), -32768, 32767
    )

    aData["TemperatureThreshhold"] = clamp(
        int( aData["TemperatureThreshhold"] ), -32768, 32767
    )

    lPacked = struct.pack(
        "<BBBBBBBBBBBBhh",
        *aData["ECGRateEvenValue"],
        *aData["ECGRateThreeValue"],
        *aData["ECGRateElseValue"],
        *aData["ECGRateDisconnectedThreshhold"],
        aData["MotionSensitiveThreshold"],
        aData["TemperatureThreshhold"]
    )

    with open( CONFIG_FILE, "wb" ) as lFile:
        lFile.write( lPacked )


def get_latest_records():
    connection = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM RecordECG ORDER BY time DESC LIMIT 10;")
            ecg_records = cursor.fetchall()

            cursor.execute("SELECT * FROM RecordMotion ORDER BY time DESC LIMIT 10;")
            motion_records = cursor.fetchall()

    finally:
        connection.close()

    return ecg_records, motion_records


#---------------------------------------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        lConfig = {
            "ECGRateEvenValue": [request.form.get(f"even_{i}", 0) for i in range(3)],
            "ECGRateThreeValue": [request.form.get(f"three_{i}", 0) for i in range(3)],
            "ECGRateElseValue": [request.form.get(f"else_{i}", 0) for i in range(3)],
            "ECGRateDisconnectedThreshhold": [request.form.get(f"disc_{i}", 0) for i in range(3)],
            "MotionSensitiveThreshold": request.form.get("motion", 0),
            "TemperatureThreshhold": request.form.get("temp", 0)
        }
        save_binary_config(lConfig)
        return redirect("/")

    lConfig = load_binary_config()
    ecg_records, motion_records = get_latest_records()
    return render_template("index.html", **lConfig, ecg_records=ecg_records, motion_records=motion_records)


if __name__ == "__main__":
    app.run(debug=True)

