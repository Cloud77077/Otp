import streamlit as st
import requests
import re
import json
from datetime import datetime

st.set_page_config(page_title="OTP Doctor Tool", layout="wide")
st.title("🔐 OTP Doctor Automation")

# ==================== API CLASS ====================
class OTPDoctor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base = "https://otpdoctor.in/stubs/handler_api.php"

    def _get(self, params):
        try:
            r = requests.get(self.base, params=params, timeout=30)
            return r.text.strip()
        except Exception as e:
            return f"ERROR: {e}"

    def get_balance(self):
        return self._get({"action": "getBalance", "api_key": self.api_key})

    def get_countries(self):
        return self._get({"action": "getCountries", "api_key": self.api_key})

    def get_services(self, country):
        return self._get({"action": "getServices", "api_key": self.api_key, "country": country})

    def get_number(self, service, country=None):
        params = {"action": "getNumber", "api_key": self.api_key, "service": service}
        if country:
            params["country"] = country
        return self._get(params)

    def get_status(self, activation_id):
        return self._get({"action": "getStatus", "api_key": self.api_key, "id": activation_id})

    def set_status(self, activation_id, status):
        return self._get({
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
    api_key_input = st.text_input("API Key", type="password", value=st.session_state.api_key)
    if st.button("Save Key"):
        st.session_state.api_key = api_key_input
        st.success("Key saved for this session")

    max_wait = st.number_input("Max wait time (seconds)", min_value=60, max_value=300, value=120, step=30)

if not st.session_state.api_key:
    st.warning("Please enter and save your API Key in the sidebar")
    st.stop()

api = OTPDoctor(st.session_state.api_key)

# ==================== BALANCE ====================
col1, col2 = st.columns([1, 3])
with col1:
    if st.button("Check Balance"):
        bal = api.get_balance()
        st.success(f"Balance: {bal}")

st.divider()

# ==================== COUNTRY & SERVICES ====================
st.subheader("1. Select Country & Load Services")

country = st.selectbox("Country", ["in", "us", "uk", "za", "iq"], index=0)

if st.button("Load Services"):
    with st.spinner("Loading services..."):
        services_raw = api.get_services(country)
        st.session_state.services_raw = services_raw

if "services_raw" in st.session_state:
    st.text_area("Raw Services Response (for debugging)", st.session_state.services_raw, height=100)

    # Try to parse services nicely
    services_dict = {}
    try:
        data = json.loads(st.session_state.services_raw)
        for sid, info in data.items():
            name = info.get("service_name", sid)
            price = info.get("service_price", "")
            services_dict[sid] = f"{sid} - {name} ({price})"
    except:
        # Fallback if not JSON
        lines = st.session_state.services_raw.replace("{", "").replace("}", "").split(",")
        for line in lines:
            if ":" in line:
                parts = line.split(":")
                sid = parts[0].strip().strip('"')
                services_dict[sid] = sid

    if services_dict:
        service_options = list(services_dict.values())
        selected_display = st.selectbox("Select Service", service_options)
        # Extract clean service ID
        selected_service = selected_display.split(" - ")[0].strip()
    else:
        selected_service = st.text_input("Enter Service ID manually (e.g. 101)")
else:
    selected_service = st.text_input("Enter Service ID manually (e.g. 101)")

# ==================== GET NUMBER ====================
st.subheader("2. Get Virtual Number")

if st.button("Get New Number", type="primary"):
    if not selected_service:
        st.error("Please select or enter a Service ID")
    else:
        with st.spinner("Buying number..."):
            response = api.get_number(selected_service, country=country)
        
        st.write(f"API Response: `{response}`")  # For debugging

        if response.startswith("ACCESS_NUMBER"):
            parts = response.split(":")
            new_num = {
                "time": datetime.now(),
                "service": selected_service,
                "phone": parts[2],
                "activation_id": parts[1],
                "otp": None,
                "status": "Waiting"
            }
            st.session_state.numbers.append(new_num)
            st.success(f"✅ Number purchased: {parts[2]}")
        else:
            st.error(f"Failed to get number. Response: {response}")

# ==================== NUMBERS LIST ====================
st.subheader("3. Your Numbers")

if not st.session_state.numbers:
    st.info("No numbers purchased yet.")
else:
    for i, num in enumerate(st.session_state.numbers):
        time_elapsed = (datetime.now() - num["time"]).seconds
        remaining = max_wait - time_elapsed

        with st.expander(f"📱 {num['phone']} | Service: {num['service']}", expanded=True):
            st.write(f"**Activation ID:** `{num['activation_id']}`")
            st.write(f"**Status:** {num['status']}")
            st.write(f"**Time Elapsed:** {time_elapsed} sec")

            if num["otp"]:
                st.success(f"**OTP:** {num['otp']}")
                st.code(num['otp'])
            else:
                if remaining > 0:
                    st.warning(f"Waiting for OTP... ({remaining}s remaining)")
                else:
                    st.error("Time limit reached!")

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Check OTP", key=f"check_{i}"):
                        status_resp = api.get_status(num["activation_id"])
                        st.write(status_resp)
                        if "STATUS_OK" in status_resp:
                            match = re.search(r'\b(\d{4,8})\b', status_resp)
                            if match:
                                num["otp"] = match.group(1)
                                num["status"] = "OTP Received"
                with c2:
                    if st.button("Cancel", key=f"cancel_{i}"):
                        api.set_status(num["activation_id"], 8)
                        num["status"] = "Cancelled"
                        st.warning("Number cancelled")
                with c3:
                    if remaining <= 0 and st.button("Cancel (Timeout)", key=f"timeout_{i}"):
                        api.set_status(num["activation_id"], 8)
                        num["status"] = "Auto Cancelled"

st.caption("Tip: You can buy multiple numbers for the same service.")
