import streamlit as st
import datetime
import psycopg2
import requests
import urllib.parse
import calendar

# ---------------- DATABASE & API CONFIG ----------------
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres.dkkxrlixzvioqdsmiwqq",
    "password": "EUCLOIDDATA1234",
    "host": "aws-0-ap-southeast-1.pooler.supabase.com",
    "port": 6543,
}

WHATSAPP_API_URL = "https://graph.facebook.com/v22.0/574132742457716/messages"
WHATSAPP_ACCESS_TOKEN = "EAAQw5b03FpsBO6oQwLSiXLV8plrYEO7gWIcMAjHOc5CMIPZCjJCenHQ7HGB0dJsJEwsWvCZC3qR6w7xXuMiN0ghiqDTJHPoDMPYlv8hrZB0xF4abdaIJ1spnHkNQq5wmp4yKvyi9tdzl6oOqdoaBlXTkCS28fHa8tgrq9hGHn3NrkuMiZAPqbScf"
full_phone = "+916379204284"

# ---------------- HELPER FUNCTIONS ----------------

def get_doctor_name(doctor_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM doctors WHERE doctor_id = %s", (doctor_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else "Unknown Doctor"

def get_patient_id(patient_name):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id FROM patients WHERE name = %s", (patient_name,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else "Unknown Patient"

def send_whatsapp_message(phone, message):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    if not phone.startswith("+"):
        phone = "+91" + phone.strip()
    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message}
    }
    response = requests.post(WHATSAPP_API_URL, json=data, headers=headers)
    return response.status_code == 200

def get_booked_slots(doctor_id, date):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT time_slot FROM appointments
        WHERE doctor_id = %s AND date = %s
    """, (doctor_id, date))
    booked = cursor.fetchall()
    cursor.close()
    conn.close()
    return [slot[0].strftime('%H:%M') for slot in booked]

def get_available_slots(doctor_id, date):
    all_slots = [f"{hour:02d}:{minute:02d}" for hour in range(9, 17) for minute in (0, 30)]
    booked_slots = get_booked_slots(doctor_id, date)
    return [slot for slot in all_slots if slot not in booked_slots]

def save_appointment(problem, date, time_slot, patient_id, doctor_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (problem, date, time_slot, status, patient_id, doctor_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (problem, date, time_slot, "Scheduled", patient_id, doctor_id))
    conn.commit()
    cursor.close()
    conn.close()

# ---------------- SESSION STATE INIT ----------------
if "selected_date" not in st.session_state:
    st.session_state.selected_date = None
if "selected_time" not in st.session_state:
    st.session_state.selected_time = None

# ---------------- UI START ----------------
# Extract query parameters
params = st.query_params
patient_name_1 = params.get("patient_name", [""])
patient_name = urllib.parse.unquote(patient_name_1)
doctor_id = params.get("doctor_id", [""])[0]
problem = params.get("problem", [""])
if not patient_name or not doctor_id:
    st.error("❌ Missing patient_name or doctor_id in URL. Use ?patient_name=NAME&doctor_id=ID")
    st.stop()

doctor_name = get_doctor_name(doctor_id)
patient_id = get_patient_id(patient_name)
st.title(f"📅 {doctor_name}'s Appointment Calendar")

st.markdown(f"👤 **Patient Name**: `{patient_name}`")
st.markdown(f"🩺 **Doctor**: `{doctor_name}`")

# ---------------- DATE SELECTION GRID ----------------
# Initialize session state
if 'selected_date' not in st.session_state:
    st.session_state.selected_date = None
if 'selected_time' not in st.session_state:
    st.session_state.selected_time = None

# ------------------- STEP 1: SELECT MONTH -------------------
st.subheader("📆 Step 1: Select a Month")

today = datetime.date.today()
months = [(today + datetime.timedelta(days=30 * i)).replace(day=1) for i in range(3)]
month_names = [month.strftime("%B %Y") for month in months]

selected_month_label = st.selectbox("Choose a month:", month_names)
month_index = month_names.index(selected_month_label)
selected_month_date = months[month_index]


# ---------------- STEP 1: SELECT MONTH ----------------
st.subheader("📅 Step 2: Select a Date")

year = selected_month_date.year
month = selected_month_date.month
_, num_days = calendar.monthrange(year, month)

# Show only weekdays
dates_in_month = [
    date for day in range(1, num_days + 1)
    if (date := datetime.date(year, month, day)).weekday() < 5 and date >= today
]


cols = st.columns(5)
for i, date in enumerate(dates_in_month):
    label = date.strftime("%a, %d %b")  # Example: Tue, 13 May
    with cols[i % 5]:
        if st.button(label):
            st.session_state.selected_date = date
            st.session_state.selected_time = None  # reset

# ------------------- STEP 3: SELECT TIME -------------------
if st.session_state.selected_date:
    st.markdown(f"### 📌 Selected Date: `{st.session_state.selected_date.strftime('%A, %d %B %Y')}`")

    available_slots = get_available_slots(doctor_id, st.session_state.selected_date)
    if available_slots:
        st.subheader("🕒 Step 3: Select a Time Slot")

        time_cols = st.columns(4)
        for i, slot in enumerate(available_slots):
            with time_cols[i % 4]:
                if st.button(slot):
                    st.session_state.selected_time = slot

        if st.session_state.selected_time:
            st.success(f"✅ Time Slot Selected: `{st.session_state.selected_time}`")

            if st.button("🔒 Confirm Appointment"):
                if not problem.strip():
                    st.warning("⚠️ Please describe the problem before booking.")
                else:
                    save_appointment(problem, st.session_state.selected_date, st.session_state.selected_time, patient_id, doctor_id)
                    st.success(f"📌 Appointment booked with {doctor_name} on {st.session_state.selected_date.strftime('%B %d')} at {st.session_state.selected_time}.")

                    message = (
                        f"Dear {patient_name},\n\n"
                        f"Your appointment is scheduled with {doctor_name} on "
                        f"{st.session_state.selected_date.strftime('%B %d, %Y')} at {st.session_state.selected_time}.\n"
                        f"Please arrive 10 minutes early.\n\n"
                        f"Thank you,\nX Hospital"
                    )
                    send_whatsapp_message(full_phone, message)
                    message = (
                        f"عزيزي {patient_name},\n\n"
                        f"تم تحديد موعدك مع{doctor_name} على"
                        f"{st.session_state.selected_date.strftime('%B %d, %Y')} at {st.session_state.selected_time}.\n"
                        f"يرجى الوصول قبل 10 دقائق.\n\n"
                        f"شكرًا لك،\n"
                        f"مستشفى إكس"
                    )
                    send_whatsapp_message(full_phone, message)
    else:
        st.warning("❌ No available slots for this date. Please choose another.")
