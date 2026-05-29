import streamlit as st
import requests
import time
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="OTP Doctor Tool", layout="wide")
st.title("🔐 OTP Doctor Automation Tool")

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

# ==================== SESSION STATE ====================
if "numbers" not in st.session_state:
    st.session_state.numbers = []

if "api_key" not in st.session_state:
    st.session_state.api_key = ""

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("⚙️ Settings")
    
    api_key_input = st.text_input("API Key", type="password", value=st.session_state.api_key)
    if st.button("Save Key"):
        st.session_state.api_key = api_key_input
        st.success("Key saved")

    max_wait = st.number_input("Max wait time per number (seconds)", 
                               min_value=30, max_value=600, value=120, step=30)
    st.caption("Default = 2 minutes (120 sec)")

    if st.session_state.api_key:
        api = OTPDoctor(st.session_state.api_key)
        if st.button("Refresh Balance"):
            bal = api.get_balance()
            st.info(f"Balance: {bal}")

st.divider()

if not st.session_state.api_key:
    st.warning("Please enter your API Key in the sidebar")
    st.stop()

api = OTPDoctor(st.session_state.api_key)

# ==================== COUNTRY & SERVICES ====================
st.subheader("1. Country & Services")

col1, col2 = st.columns(2)
with col1:
    country = st.selectbox("Country", ["in", "us", "uk", "za", "iq"], index=0)

with col2:
    if st.button("Load Services"):
        services = api.get_services(country)
        st.session_state.services = services
        st.rerun()

if "services" in st.session_state:
    search = st.text_input("Search services (whatsapp, telegram, etc.)")
    services_list = st.session_state.services.split(",") if isinstance(st.session_state.services, str) else []
    
    if search:
        filtered = [s for s in services_list if search.lower() in s.lower()]
    else:
        filtered = services_list[:40]
    
    selected_service = st.selectbox("Select Service", filtered if filtered else ["No services"])
else:
    selected_service = st.text_input("Enter Service ID manually (e.g. 101)")

# ==================== GET NUMBER ====================
st.subheader("2. Get New Number")

if st.button("Get New Number", type="primary"):
    if not selected_service or selected_service == "No services":
        st.error("Please select a valid service")
    else:
        with st.spinner("Purchasing number..."):
            response = api.get_number(selected_service, country=country)
        
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
            st.error(f"Failed: {response}")

# ==================== NUMBERS LIST ====================
st.subheader("3. Your Numbers (Multiple for same service)")

if not st.session_state.numbers:
    st.info("No numbers yet. Buy one above.")
else:
    # Check All button
    if st.button("Check All Pending OTPs"):
        for num in st.session_state.numbers:
            if num["otp"] is None and num["status"] == "Waiting":
                status_resp = api.get_status(num["activation_id"])
                if "STATUS_OK" in status_resp:
                    match = re.search(r'\b(\d{4,8})\b', status_resp)
                    if match:
                        num["otp"] = match.group(1)
                        num["status"] = "OTP Received"
        st.rerun()

    for i, num in enumerate(st.session_state.numbers):
        time_elapsed = (datetime.now() - num["time"]).seconds
        remaining = max_wait - time_elapsed

        with st.expander(f"📱 {num['phone']} | {num['service']} | {num['time'].strftime('%H:%M')}", expanded=True):
            st.write(f"**Activation ID:** `{num['activation_id']}`")
            st.write(f"**Status:** {num['status']}")
            st.write(f"**Time Elapsed:** {time_elapsed} sec")

            if num["otp"]:
                st.success(f"OTP: {num['otp']}")
                st.code(num['otp'], language="text")
            else:
                if remaining > 0:
                    st.warning(f"Waiting... {remaining} sec remaining (max {max_wait}s)")
                else:
                    st.error("Time exceeded 2 minutes!")

                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("Check OTP", key=f"check_{i}"):
                        status_resp = api.get_status(num["activation_id"])
                        st.write(status_resp)
                        if "STATUS_OK" in status_resp:
                            match = re.search(r'\b(\d{4,8})\b', status_resp)
                            if match:
                                num["otp"] = match.group(1)
                                num["status"] = "OTP Received"
                                st.success(f"OTP Found: {num['otp']}")
                
                with col2:
                    if st.button("Cancel Number", key=f"cancel_{i}"):
                        api.set_status(num["activation_id"], 8)
                        num["status"] = "Cancelled"
                        st.warning("Number cancelled")
                
                with col3:
                    if remaining <= 0 and st.button("Auto Cancel (Timeout)", key=f"timeout_{i}"):
                        api.set_status(num["activation_id"], 8)
                        num["status"] = "Auto Cancelled (Timeout)"
                        st.error("Cancelled due to timeout")

st.divider()
st.caption("You can buy multiple numbers for the same service. They will all appear above.")
