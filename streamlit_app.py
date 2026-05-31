import streamlit as st
import requests
import re
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup

st.set_page_config(page_title="OTP Doctor Tool", layout="wide")
st.title("🔐 OTP Doctor Automation Tool")

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

# ==================== AUTO OPERATOR CHECK (REBTEL) ====================
def get_operator_rebtel(phone_number):
    try:
        clean = phone_number.replace("+91", "").strip()
        url = f"https://www.rebtel.com/en/recharge/india/products?msisdn=+91{clean}"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=12)
        
        if resp.status_code != 200:
            return "Check failed"
        
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text().lower()
        
        if "jio" in text:
            return "Jio"
        elif "airtel" in text:
            return "Airtel"
        elif "vi" in text or "vodafone" in text or "idea" in text:
            return "Vi"
        elif "bsnl" in text:
            return "BSNL"
        else:
            return "Unknown / Not detected"
    except:
        return "Error checking"

# ==================== SESSION ====================
if "numbers" not in st.session_state:
    st.session_state.numbers = []
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("API Key", type="password", value=st.session_state.api_key)
    if st.button("Save Key"):
        st.session_state.api_key = api_key
        st.success("Saved")

    max_wait = st.slider("Max wait time", 60, 300, 120)

if not st.session_state.api_key:
    st.warning("Enter API Key in sidebar")
    st.stop()

api = OTPDoctor(st.session_state.api_key)

if st.button("Check Balance"):
    st.info(api.get_balance())

st.divider()

# Service
st.subheader("Service")
country = st.selectbox("Country", ["in", "us", "uk", "za", "iq"], index=0)
manual_service = st.text_input("Service ID (e.g. 101)", placeholder="101")

# Get Number
st.subheader("Get Number")

if st.button("Get New Number"):
    if not manual_service:
        st.error("Enter Service ID")
    else:
        response = api.get_number(manual_service, country=country)
        if response.startswith("ACCESS_NUMBER"):
            parts = response.split(":")
            phone = parts[2]
            
            # === AUTO CHECK OPERATOR ===
            with st.spinner("Checking operator..."):
                operator = get_operator_rebtel(phone)
            
            st.session_state.numbers.append({
                "time": datetime.now(),
                "service": manual_service,
                "phone": phone,
                "activation_id": parts[1],
                "otp": None,
                "status": "Waiting",
                "operator": operator
            })
            st.success(f"Got number: {phone} | Operator: {operator}")
        else:
            st.error(f"Failed: {response}")

# Auto Retry
if st.button("Auto Retry Until Success"):
    if not manual_service:
        st.error("Enter Service ID")
    else:
        for attempt in range(1, 9):
            response = api.get_number(manual_service, country=country)
            if response.startswith("ACCESS_NUMBER"):
                parts = response.split(":")
                phone = parts[2]
                
                with st.spinner("Checking operator..."):
                    operator = get_operator_rebtel(phone)
                
                st.session_state.numbers.append({
                    "time": datetime.now(),
                    "service": manual_service,
                    "phone": phone,
                    "activation_id": parts[1],
                    "otp": None,
                    "status": "Waiting",
                    "operator": operator
                })
                st.success(f"Success! {phone} | Operator: {operator}")
                break
            time.sleep(2)

# Show Numbers
st.subheader("Your Numbers")

if not st.session_state.numbers:
    st.info("No numbers yet")
else:
    for i, num in enumerate(st.session_state.numbers):
        with st.expander(f"📱 {num['phone']} | {num['service']}", expanded=True):
            st.write(f"**Operator:** {num.get('operator', 'Not checked')}")
            st.write(f"**Activation ID:** `{num['activation_id']}`")
            st.write(f"**Status:** {num['status']}")

            if num["otp"]:
                st.success(f"OTP: {num['otp']}")
            else:
                if st.button("Check OTP", key=f"otp_{i}"):
                    status = api.get_status(num["activation_id"])
                    if "STATUS_OK" in status:
                        match = re.search(r'\b(\d{4,8})\b', status)
                        if match:
                            num["otp"] = match.group(1)

            if st.button("Cancel", key=f"cancel_{i}"):
                api.set_status(num["activation_id"], 8)
                num["status"] = "Cancelled"

st.caption("Operator is now checked automatically when you get a number.")
