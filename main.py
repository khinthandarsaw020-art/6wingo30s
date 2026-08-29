import requests
import time
import json
import os
import threading
from collections import deque
from flask import Flask

# ==========================================
# Telegram နဲ့ Supabase အချက်အလက်များ
# ==========================================
TELEGRAM_TOKEN = "8782457950:AAHbd-J29Y0fKhcBOHbSnn1d4z4vhiDQLKg" 
CHAT_ID = "8745116942"

SUPABASE_URL = "https://xdhhakpsonirkpimctlw.supabase.co"
SUPABASE_KEY = "sb_publishable_bVJj1lqSAsIQ1kQ8Ae2vAQ_o3yCjDeA"
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Wingo AI Bot with Supabase is Running 24/7!"

class PersistentHybridAgent:
    def __init__(self):
        self.window = deque(maxlen=7)
        self.martingale_steps = [1, 2, 4, 8, 16, 32]
        self.current_step = 0
        self.active_prediction = None
        self.last_state = None
        
        self.best_threshold = 0.65
        self.lr = 0.1
        self.epsilon = 0.1
        
        self.q_table = self.load_q_table()

    def load_q_table(self):
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        try:
            res = requests.get(f"{SUPABASE_URL}/rest/v1/q_table?select=*", headers=headers)
            if res.status_code == 200:
                data = res.json()
                q_dict = {}
                for row in data:
                    q_dict[row['state']] = row['actions']
                print(f"📂 Supabase မှ AI ရဲ့ မှတ်ဉာဏ်များ ({len(q_dict)} states) ကို ဖတ်ရှုပြီးပါပြီ။")
                return q_dict
        except Exception as e:
            print(f"⚠️ Supabase မှ ဖတ်ရာတွင် အမှားရှိသည်။: {e}")
        return {}

    def save_q_table(self, state, actions):
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        payload = {
            "state": state,
            "actions": actions
        }
        try:
            requests.post(f"{SUPABASE_URL}/rest/v1/q_table", headers=headers, json=payload)
        except Exception as e:
            pass

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            pass

    def get_state_key(self):
        return ",".join(list(self.window))

    def get_q_action(self, state):
        if state not in self.q_table:
            self.q_table[state] = {"Big": 0.0, "Small": 0.0}
        
        actions = self.q_table[state]
        if actions["Big"] > actions["Small"]:
            return "Big"
        elif actions["Small"] > actions["Big"]:
            return "Small"
        return None

    def update_q_table(self, state, action, reward):
        if state not in self.q_table:
            self.q_table[state] = {"Big": 0.0, "Small": 0.0}
        old_q = self.q_table[state][action]
        self.q_table[state][action] = old_q + self.lr * (reward - old_q)
        
        self.save_q_table(state, self.q_table[state])

    def analyze_round(self, period, current_result):
        if self.active_prediction and self.last_state:
            predicted = self.active_prediction
            reward = 0
            
            if current_result.lower() == predicted.lower():
                reward = 1.5
                self.current_step = 0
                self.send_telegram(f"✅ <b>HYBRID WIN!</b> Period {period} တွင် {current_result} ထွက်၍ အနိုင်ရပါသည်။ Step 1 သို့ ပြန်မည်။")
            else:
                reward = -1.5
                self.current_step += 1
                if self.current_step >= len(self.martingale_steps):
                    self.send_telegram("⚠️ <b>6x HARD STOP!</b> ၆ ကြိမ် ဆက်တိုက် ရှုံးသွားပါသည်။ Step 1 သို့ Reset ချပါသည်။")
                    self.current_step = 0
                self.send_telegram(f"❌ <b>HYBRID LOSS!</b> Period {period} တွင် {current_result} ထွက်သွားပါသည်။")
            
            self.update_q_table(self.last_state, predicted, reward)
            self.active_prediction = None

        self.window.append(current_result)
        
        if len(self.window) < 7:
            return

        total_rounds = len(self.window)
        big_count = sum(1 for x in self.window if str(x).lower() == "big")
        small_count = total_rounds - big_count
        
        big_ratio = big_count / total_rounds
        small_ratio = small_count / total_rounds
        pressure_val = abs(big_ratio - small_ratio)

        manus_prediction = None
        regime = "Sideways"

        if big_ratio >= self.best_threshold:
            regime = "Uptrend (Big Pressure)"
            manus_prediction = "Big"
        elif small_ratio >= self.best_threshold:
            regime = "Downtrend (Small Pressure)"
            manus_prediction = "Small"

        current_state = self.get_state_key()
        q_prediction = self.get_q_action(current_state)

        final_prediction = None
        if manus_prediction and q_prediction:
            if manus_prediction == q_prediction:
                final_prediction = manus_prediction
        elif manus_prediction:
            final_prediction = manus_prediction

        if final_prediction:
            self.last_state = current_state
            self.active_prediction = final_prediction
            multiplier = self.martingale_steps[self.current_step]
            
            msg = (
                f"🔥 <b>PERSISTENT HYBRID AI | Period: {period}</b>\n\n"
                f"📈 Manus Regime: <b>{regime}</b>\n"
                f"⚖️ Pressure Val: <b>{pressure_val:.2f}</b>\n"
                f"🧠 Cloud Memory: <b>Active ({len(self.q_table)} states)</b>\n\n"
                f"🎯 <b>လောင်းရမည့်ဘက်:</b> {final_prediction.upper()}\n"
                f"💰 <b>Martingale:</b> Step {self.current_step + 1} ({multiplier}x)"
            )
            self.send_telegram(msg)
        else:
            wait_msg = (
                f"⏳ <b>AI WAITING | Period: {period}</b>\n\n"
                f"📊 Market Trend: <b>{regime} (Not strong enough)</b>\n"
                f"⚖️ Pressure Val: <b>{pressure_val:.2f}</b>\n"
                f"💬 <i>အခြေအနေ မသေချာသေးပါသဖြင့် ခဏစောင့်ဆိုင်းနေပါသည်...</i>"
            )
            self.send_telegram(wait_msg)

def run_bot():
    agent = PersistentHybridAgent()
    last_period = ""
    print("🚀 Supabase ချိတ်ဆက်ထားသော Persistent Hybrid AI Agent စတင် အလုပ်လုပ်နေပါပြီ...")
    
    url = "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList"
    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOiIxNzg3OTgxNTA5IiwibmJmIjoiMTc4Nzk4MTUwOSIsImV4cCI6IjE3ODc5ODMzMDkiLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL2V4cGlyYXRpb24iOiI4LzI5LzIwMjYgMTI6MzE6NDkgUE0iLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJBY2Nlc3NfVG9rZW4iLCJVc2VySWQiOiIxMDEyMjEzIiwiVXNlck5hbWUiOiI5NTk3NDA5MzkzNzAiLCJVc2VyUGhvdG8iOiI5IiwiTmlja05hbWUiOiJUaetsR3lpIiwiQW1vdW50IjoiODcuMzAiLCJJbnRlZ3JhbCI6IjAiLCJMb2dpbk1hcmsiOiJINSIsIkxvZ2luVGltZSI6IjgvMjkvMjAyNiAxMjowMTo0OSBQTSIsIjxvZ2luSVBBZGRyZXNzIjoiNDUuNDEuMTA0LjI0MCIsImRiTnVtYmVyIjoiMCIsIklzdmFsaWRhdG9yIjoiMCIsIktleUNvZGUiOiIzMjMzMiIsIlRva2VuVHlwZSI6IkFjY2Vzc19Ub2tlbiIsImPhG9uZVR5cGUiOiIwIiwiVXNlclR5cGUiOiIwIiwiVXNlclR5c2UyOiIiLCJpc3MiOiJqd3RJc3N1ZXIiOiJhdWQiOiJsb3R0ZXJ5VGlja2V0In0.ZL0Y9gexUTCsKwWeZhCLAAw8AABEYJt0GnIzIviMG4g",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://6win598.com",
        "referer": "https://6win598.com/",
        "user-agent": "Mozilla/5.0"
    }
    payload = {
        "pageSize": 10, "pageNo": 1, "typeId": 30, "language": 7,
        "random": "036263f367384d418be07465793c8da8",
        "signature": "55F4FD150F15F090B943374F3C9BE78B",
        "timestamp": 1787981526
    }
    
    while True:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=3)
            data = response.json()
            list_data = data.get("data", {}).get("list", [])
            if len(list_data) > 0:
                latest_round = list_data[0]
                raw_period = str(latest_round.get("issueNumber"))
                current_period = str(int(raw_period) + 2)
                number = int(latest_round.get("number"))
                current_result = "Big" if number >= 5 else "Small"
                
                if current_period != last_period:
                    last_period = current_period
                    agent.analyze_round(current_period, current_result)
        except Exception as e:
            pass
        time.sleep(0.5)

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
