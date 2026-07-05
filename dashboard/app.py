import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------
# Page Configuration
# ---------------------------------------
st.set_page_config(
    page_title="ZTII Dashboard",
    page_icon="🏭",
    layout="wide"
)

# Auto refresh every 3 seconds
st_autorefresh(interval=3000, key="refresh")

API_URL = "http://127.0.0.1:8000"

# ---------------------------------------
# Title
# ---------------------------------------
st.title("🏭 Zero-Touch Industrial Intelligence")
st.write("### Industrial Device Monitoring Dashboard")

# ---------------------------------------
# Get Data from FastAPI
# ---------------------------------------
try:
    response = requests.get(f"{API_URL}/devices")

    if response.status_code != 200:
        st.error("Failed to retrieve data from FastAPI.")
        st.stop()

    devices = response.json()

    if devices:

        rows = []

        for device_id, info in devices.items():

            temperature = info["temperature"]
            vibration = info["vibration"]

            # Device Health
            if temperature > 35:
                health = "🔴 Overheat"
            elif vibration > 2.0:
                health = "🟠 High Vibration"
            else:
                health = "🟢 Normal"

            rows.append({
                "Device ID": device_id,
                "Temperature (°C)": temperature,
                "Vibration": vibration,
                "Status": info["status"],
                "Health": health,
                "Registered At": info["registered_at"]
            })

        df = pd.DataFrame(rows)

        # ---------------------------------------
        # Dashboard Metrics
        # ---------------------------------------
        st.subheader("📊 System Overview")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("🏭 Total Devices", len(df))

        with col2:
            st.metric(
                "🌡️ Avg Temperature",
                f"{df['Temperature (°C)'].mean():.2f} °C"
            )

        with col3:
            st.metric(
                "📳 Avg Vibration",
                f"{df['Vibration'].mean():.2f}"
            )

        with col4:
            online = (df["Status"] == "Online").sum()
            st.metric("🟢 Online", online)

        st.divider()

        # ---------------------------------------
        # Registered Devices
        # ---------------------------------------
        st.subheader("📡 Registered Devices")

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # ---------------------------------------
        # Temperature Chart
        # ---------------------------------------
        st.subheader("🌡️ Temperature by Device")

        temp_chart = df.set_index("Device ID")["Temperature (°C)"]

        st.bar_chart(temp_chart)

        st.divider()

        # ---------------------------------------
        # Vibration Chart
        # ---------------------------------------
        st.subheader("📳 Vibration by Device")

        vib_chart = df.set_index("Device ID")["Vibration"]

        st.bar_chart(vib_chart)

        st.divider()

        # =======================================
        # Historical Analytics
        # =======================================
        st.subheader("📈 Historical Analytics")

        device_list = list(devices.keys())

        selected_device = st.selectbox(
            "Select Device",
            device_list
        )

        history_response = requests.get(
            f"{API_URL}/history/{selected_device}"
        )

        if history_response.status_code == 200:

            history = history_response.json()

            if history:

                history_df = pd.DataFrame(history)

                history_df["recorded_at"] = pd.to_datetime(
                    history_df["recorded_at"]
                )

                history_df = history_df.sort_values(
                    "recorded_at"
                )

                # ---------------------------------------
                # Temperature History
                # ---------------------------------------
                st.subheader("🌡️ Temperature History")

                temp_history = history_df.set_index(
                    "recorded_at"
                )["temperature"]

                st.line_chart(temp_history)

                st.divider()

                # ---------------------------------------
                # Vibration History
                # ---------------------------------------
                st.subheader("📳 Vibration History")

                vibration_history = history_df.set_index(
                    "recorded_at"
                )["vibration"]

                st.line_chart(vibration_history)

                st.divider()

                # ---------------------------------------
                # Latest Reading
                # ---------------------------------------
                st.subheader("📄 Latest Reading")

                latest = history_df.iloc[-1]

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "🌡️ Temperature",
                        f"{latest['temperature']:.2f} °C"
                    )

                with col2:
                    st.metric(
                        "📳 Vibration",
                        f"{latest['vibration']:.2f}"
                    )

                with col3:
                    st.metric(
                        "🕒 Recorded At",
                        latest["recorded_at"].strftime("%Y-%m-%d %H:%M:%S")
                    )

            else:
                st.info("No historical data available.")

        else:
            st.error("Unable to retrieve historical data.")

    else:
        st.warning("No registered devices found.")

except requests.exceptions.ConnectionError:
    st.error(
        "❌ Cannot connect to FastAPI backend.\n\n"
        "Make sure FastAPI is running:\n\n"
        "python -m uvicorn backend.main:app --reload"
    )

except Exception as e:
    st.error(f"Unexpected error:\n\n{e}")