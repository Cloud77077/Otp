import streamlit as st
import requests
import re
import json
import time
from datetime import datetime

st.set_page_config(page_title="OTP Doctor Tool", layout="wide")
st.title("🔐 OTP Doctor Automation Tool")

# ==================== API CLASS ====================
class OTPDoctor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base = "https://otpdoctor.in/stubs/handler_api.php"

    def _request(self, params):
        try:
            r = requests.get(self.base, params=params, timeout=30)
            return r.text.strip()
        except Exception as e:
            return f"ERROR: {str(e)}"

    def get_balance(self):
        return self._request({"action": "getBalance", "api_key": self.api_key})

    def get_countries(self):
        return self._request({"action": "getCountries", "api_key": self.api_key})

    def get_services(self, country):
        return self._request({"action": "getServices", "api_key": self.api_key, "country": country})

    def get_number(self, service, country=None):
        params = {"action": "getNumber", "api_key": self.api_key, "service": service}
        if country:
            params["country"] = country
        return self._request(params)

    def get_status(self, activation_id):
        return self._request({"action": "getStatus", "api_key": self.api_key, "id": activation_id})

    def set_status(self, activation_id, status):
        return self._request({
            "action": "setStatus",
            "api_key": self.api_key,
            "id": activation_id,
            "status": status
        })

# ==================== SESSION ====================
if "numbers" not in st.session_state:
    st.session_state.numbers = []
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("API Key", type="password", value=st.session_state.api_key)
    if st.button("Save Key"):
        st.session_state.api_key = api_key
        st.success("Key saved")

    max_wait = st.slider("Max wait time per number (sec)", 60, 300, 120)
    max_auto_attempts = st.slider("Max auto retry attempts", 3, 15, 8)

if not st.session_state.api_key:
    st.warning("Enter your API Key in the sidebar")
    st.stop()

api = OTPDoctor(st.session_state.api_key)

# Balance
if st.button("Check Balance"):
    st.info(api.get_balance())

st.divider()

# ==================== SERVICES ====================
st.subheader("1. Country & Services")

country = st.selectbox("Country", ["in", "us", "uk", "za", "iq"], index=0)

if st.button("Load Services"):
    raw = api.get_services(country)
    st.session_state.services_raw = raw

if "services_raw" in st.session_state:
    with st.expander("Raw Services Response"):
        st.code(st.session_state.services_raw)

# Service Selection
st.write("**Select Service**")

manual_id = st.text_input("Enter Service ID manually (Recommended)", placeholder="101, 102, etc.")

# Try to show nice list from API
service_options = []
if "services_raw" in st.session_state:
    try:
        data = json.loads(st.session_state.services_raw)
        for sid, info in data.items():
            name = info.get("service_name", sid)
            price = info.get("service_price", "")
            service_options.append(f"{sid} - {name} ({price})")
    except:
        pass

if service_options:
    selected = st.selectbox("Or select from list", service_options)
    auto_id = selected.split(" - ")[0].strip()
else:
    auto_id = ""

# Final service ID
final_service = manual_id if manual_id else auto_id

if final_service:
    st.success(f"Using Service ID: **{final_service}**")

# ==================== GET NUMBER (NORMAL + AUTO RETRY) ====================
st.subheader("2. Get Number")

col1, col2 = st.columns(2)

with col1:
    if st.button("Get New Number (Single Try)"):
        if not final_service:
            st.error("Please enter/select a Service ID")
        else:
            response = api.get_number(final_service, country=country)
            st.write(f"Response: `{response}`")

            if response.startswith("ACCESS_NUMBER"):
                parts = response.split(":")
                st.session_state.numbers.append({
                    "time": datetime.now(),
                    "service": final_service,
                    "phone": parts[2],
                    "activation_id": parts[1],
                    "otp": None,
                    "status": "Waiting"
                })
                st.success(f"✅ Got number: {parts[2]}")
            else:
                st.error(f"Failed: {response}")

with col2:
    if st.button("Auto Retry Until Number Available"):
        if not final_service:
            st.error("Enter Service ID first")
        else:
            st.write("Starting auto retry...")
            progress = st.progress(0)
            status_text = st.empty()

            for attempt in range(1, max_auto_attempts + 1):
                status_text.write(f"Attempt {attempt}/{max_auto_attempts}...")
                response = api.get_number(final_service, country=country)

                if response.startswith("ACCESS_NUMBER"):
                    parts = response.split(":")
                    st.session_state.numbers.append({
                        "time": datetime.now(),
                        "service": final_service,
                        "phone": parts[2],
                        "activation_id": parts[1],
                        "otp": None,
                        "status": "Waiting"
                    })
                    st.success(f"✅ Success on attempt {attempt}! Number: {parts[2]}")
                    progress.progress(100)
                    break
                else:
                    progress.progress(int((attempt / max_auto_attempts) * 100))
                    if attempt < max_auto_attempts:
                        time.sleep(3)  # wait 3 seconds before next try
                    else:
                        st.error(f"Failed after {max_auto_attempts} attempts. Last response: {response}")

# ==================== YOUR NUMBERS ====================
st.subheader("3. Your Numbers")

if not st.session_state.numbers:
    st.info("No numbers yet.")
else:
    for i, num in enumerate(st.session_state.numbers):
        elapsed = (datetime.now() - num["time"]).seconds
        remaining = max_wait - elapsed

        with st.expander(f"📱 {num['phone']} | {num['service']}", expanded=True):
            st.write(f"**Activation ID:** `{num['activation_id']}`")
            st.write(f"**Status:** {num['status']}")
            st.write(f"**Time Elapsed:** {elapsed} sec")

            if num["otp"]:
                st.success(f"OTP: {num['otp']}")
                st.code(num["otp"])
            else:
                if remaining > 0:
                    st.warning(f"Waiting... {remaining}s remaining")
                else:
                    st.error("Time limit reached!")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Check OTP", key=f"check_{i}"):
                        status = api.get_status(num["activation_id"])
                        st.write(status)
                        if "STATUS_OK" in status:
                            match = re.search(r'\b(\d{4,8})\b', status)
                            if match:
                                num["otp"] = match.group(1)
                                num["status"] = "OTP Received"
                with c2:
                    if st.button("Cancel Number", key=f"cancel_{i}"):
                        api.set_status(num["activation_id"], 8)
                        num["status"] = "Cancelled"
                        st.warning("Cancelled")

st.caption("Tip: Use 'Auto Retry' when numbers are limited for a service.")
