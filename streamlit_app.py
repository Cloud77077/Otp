import streamlit as st
import requests
import re
import time
import json
from datetime import datetime
from bs4 import BeautifulSoup

st.set_page_config(page_title="OTP Doctor Tool", layout="wide")
st.title("🔐 OTP Doctor Automation Tool")

class OTPDoctor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base = "https://otpdoctor.in/stubs/handler_api.php"

    def _get(self, params):
        try:
            r = requests.get(self.base, params=params, timeout=30)
            return r.text.strip()
        except Exception as e:
            return f"ERROR: {str(e)}"

    def get_balance(self):
        return self._get({"action": "getBalance", "api_key": self.api_key})

    def get_services(self, country):
        return self._get({
            "action": "getServices",
            "api_key": self.api_key,
            "country": country
        })

    def get_number(self, service, country="in"):
        return self._get({
            "action": "getNumber",
            "api_key": self.api_key,
            "service": service,
            "country": country
        })

    def get_status(self, activation_id):
        return self._get({
            "action": "getStatus",
            "api_key": self.api_key,
            "id": activation_id
        })

    def set_status(self, activation_id, status):
        return self._get({
            "action": "setStatus",
            "api_key": self.api_key,
            "id": activation_id,
            "status": status
        })

# ==================== IMPROVED REBTEL TEXT + LOGO DETECTION ====================
def get_rebtel_info(phone):
    try:
        clean = phone.replace("+", "").replace(" ", "").strip()
        if clean.startswith("91") and len(clean) > 10:
            clean = clean[2:]

        url = f"https://www.rebtel.com/en/recharge/india/products?msisdn=+91{clean}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=12)

        if resp.status_code != 200:
            return {"operator": "Check failed", "logo_url": None}

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text().lower()
        raw = resp.text.lower()

        # Try to find logo first (most reliable when available)
        logo_url = None
        for img in soup.find_all("img"):
            src = img.get("src", "").lower()
            alt = (img.get("alt", "") + " " + img.get("title", "")).lower()
            
            if "jio" in src + alt:
                logo_url = img.get("src")
                if not logo_url.startswith("http"):
                    logo_url = "https://www.rebtel.com" + logo_url
                return {"operator": "Jio", "logo_url": logo_url}
            elif "airtel" in src + alt:
                logo_url = img.get("src")
                if not logo_url.startswith("http"):
                    logo_url = "https://www.rebtel.com" + logo_url
                return {"operator": "Airtel", "logo_url": logo_url}
            elif "bsnl" in src + alt:
                logo_url = img.get("src")
                if not logo_url.startswith("http"):
                    logo_url = "https://www.rebtel.com" + logo_url
                return {"operator": "BSNL", "logo_url": logo_url}

        # Text-based detection with better priority (focus on clear text)
        if "jio" in text:
            return {"operator": "Jio", "logo_url": logo_url}
        if "airtel" in text:
            return {"operator": "Airtel", "logo_url": logo_url}
        if "bsnl" in text:
            return {"operator": "BSNL", "logo_url": logo_url}

        # Vi only with strong evidence (to avoid false positives)
        vi_count = text.count("vi ") + text.count("vodafone") + text.count("idea")
        if vi_count >= 4:
            return {"operator": "Vi", "logo_url": logo_url}

        return {"operator": "Unknown", "logo_url": logo_url}
    except:
        return {"operator": "Error", "logo_url": None}

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
        st.success("Key saved")

if not st.session_state.api_key:
    st.warning("Enter your API Key in the sidebar")
    st.stop()

api = OTPDoctor(st.session_state.api_key)

if st.button("Check Balance"):
    st.info(api.get_balance())

st.divider()

# ==================== SERVICES ====================
st.subheader("1. Services")

country = st.selectbox("Country", ["in", "us", "uk", "za", "iq"], index=0)

if st.button("Load Services"):
    with st.spinner("Loading..."):
        raw = api.get_services(country)
        st.session_state.services_raw = raw

if "services_raw" in st.session_state:
    try:
        data = json.loads(st.session_state.services_raw)
        formatted = [f"{sid} - {info.get('service_name', sid)} ({info.get('service_price', '')})" 
                     for sid, info in data.items()]
        if formatted:
            st.selectbox("Services", formatted)
    except:
        with st.expander("Raw Services"):
            st.code(st.session_state.services_raw)

service_id = st.text_input("Service ID", placeholder="101")

# ==================== GET NUMBER ====================
st.subheader("2. Get Number")

col1, col2 = st.columns(2)

with col1:
    if st.button("Get New Number"):
        if not service_id:
            st.error("Enter Service ID")
        else:
            response = api.get_number(service_id)
            if response.startswith("ACCESS_NUMBER"):
                parts = response.split(":")
                phone = parts[2]
                info = get_rebtel_info(phone)
                
                st.session_state.numbers.append({
                    "time": datetime.now(),
                    "service": service_id,
                    "phone": phone,
                    "activation_id": parts[1],
                    "otp": None,
                    "status": "Waiting",
                    "operator": info["operator"],
                    "logo_url": info["logo_url"]
                })
                st.success(f"Got: {phone}")

with col2:
    if st.button("Auto Retry Until Success"):
        if not service_id:
            st.error("Enter Service ID")
        else:
            for _ in range(8):
                response = api.get_number(service_id)
                if response.startswith("ACCESS_NUMBER"):
                    parts = response.split(":")
                    phone = parts[2]
                    info = get_rebtel_info(phone)
                    
                    st.session_state.numbers.append({
                        "time": datetime.now(),
                        "service": service_id,
                        "phone": phone,
                        "activation_id": parts[1],
                        "otp": None,
                        "status": "Waiting",
                        "operator": info["operator"],
                        "logo_url": info["logo_url"]
                    })
                    st.success(f"Success! {phone}")
                    break
                time.sleep(2)

# ==================== YOUR NUMBERS ====================
st.subheader("3. Your Numbers")

if not st.session_state.numbers:
    st.info("No numbers yet")
else:
    for i, num in enumerate(st.session_state.numbers):
        with st.expander(f"📱 {num['phone']} | {num['service']}", expanded=True):
            
            # Logo or Badge
            if num.get("logo_url"):
                try:
                    st.image(num["logo_url"], width=90)
                except:
                    pass
            else:
                operator = num.get("operator", "Unknown")
                color = {"Airtel":"#FF0000", "Jio":"#00A8E8", "BSNL":"#228B22", "Vi":"#FF6600"}.get(operator, "#888888")
                st.markdown(f"**Operator:** <span style='background-color:{color};color:white;padding:4px 10px;border-radius:5px;font-weight:bold'>{operator}</span>", unsafe_allow_html=True)

            st.write(f"**Activation ID:** `{num['activation_id']}`")
            st.write(f"**Status:** {num['status']}")

            clean = num['phone'].replace("+", "").replace(" ", "")
            if clean.startswith("91") and len(clean) > 10:
                clean = clean[2:]
            st.markdown(f"[Open in Rebtel](https://www.rebtel.com/en/recharge/india/products?msisdn=+91{clean})")

            if num["otp"]:
                st.success(f"OTP: {num['otp']}")
                st.code(num["otp"])
            else:
                if st.button("Check OTP", key=f"otp_{i}"):
                    status = api.get_status(num["activation_id"])
                    st.write(f"Raw Response: `{status}`")
                    if "STATUS_OK" in status:
                        match = re.search(r'\b(\d{4,8})\b', status)
                        if match:
                            num["otp"] = match.group(1)
                            num["status"] = "OTP Received"
                            st.success(f"OTP Found: {num['otp']}")

            if st.button("Cancel Number", key=f"cancel_{i}"):
                api.set_status(num["activation_id"], 8)
                num["status"] = "Cancelled"
                st.warning("Cancelled")

st.caption("Improved text + logo detection from Rebtel")
