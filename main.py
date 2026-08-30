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
CHAT_ID = "-1003917249143"

SUPABASE_URL = "https://xdhhakpsonirkpimctlw.supabase.co"
SUPABASE_KEY = "sb_publishable_bVJj1lqSAsIQ1kQ8Ae2vAQ_o3yCjDeA"
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Pro Trading Strategy Dual-Agent AI Bot is Running 24/7!"

class DualAgentEnsemble:
    def __init__(self):
        self.window = deque(maxlen=7)
        
        # 💰 Infinite Martingale Flow (1x, 2x, 4x, 8x, 16x, 32x, 64x, 128x ... အဆုံးမရှိတက်မည်၊ နိုင်မှသာ 1x သို့ ပြန်ဆင်းမည်)
        self.current_step = 0 # 0 ဆိုသည်မှာ 1x ဖြစ်သည် (Index အလိုက် မြှောက်မည်)
        
        self.active_prediction = None
        self.last_state = None
        
        # 🧠 Trading Strategy Settings
        self.lr = 0.35
        self.q_table = self.load_q_table()

    def get_current_multiplier(self):
        # Step 0 = 1x, Step 1 = 2x, Step 2 = 4x, Step 3 = 8x, Step 4 = 16x, Step 5 = 32x, Step 6 = 64x, Step 7 = 128x ...
        return 2 ** self.current_step

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
                print(f"📂 Supabase မှ Strategy Memory ({len(q_dict)} states) ကို ဖတ်ရှုပြီးပါပြီ။")
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

    # 📈 Strategy 1: Exponential Momentum (Trend Specialist)
    def agent_trend_momentum(self, recent_list):
        weights = [1.0, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0]
        score_big = 0
        score_small = 0
        total_weight = sum(weights[-len(recent_list):])
        
        for i, val in enumerate(recent_list):
            w = weights[len(weights) - len(recent_list) + i]
            if str(val).lower() == "big":
                score_big += w
            else:
                score_small += w
                
        big_ratio = score_big / total_weight
        small_ratio = score_small / total_weight
        
        if big_ratio >= 0.60:
            return "Big", f"EMA Uptrend ({big_ratio*100:.0f}%)"
        elif small_ratio >= 0.60:
            return "Small", f"EMA Downtrend ({small_ratio*100:.0f}%)"
        return None, "EMA Neutral"

    # 📉 Strategy 2: Mean Reversion (Sideways/Correction Specialist)
    def agent_mean_reversion(self, recent_list, state):
        last_three = [str(x).lower() for x in recent_list[-3:]]
        
        if last_three.count("big") == 3:
            return "Small", "Mean Reversion (Overbought Correction)"
        elif last_three.count("small") == 3:
            return "Big", "Mean Reversion (Oversold Correction)"
        else:
            q_act = self.get_q_action(state)
            if q_act:
                return q_act, "Q-Table Reversion Memory"
        return None, "Reversion Standby"

    def analyze_round(self, period, current_result):
        short_period = "..." + str(period)[-3:] if len(str(period)) >= 3 else "..." + str(period)

        # 1. Learning & Reward Processing
        if self.active_prediction and self.last_state:
            predicted = self.active_prediction
            reward = 0
            
            if current_result.lower() == predicted.lower():
                reward = 4.0 if self.current_step == 0 else 3.0
                self.current_step = 0  # 🏆 နိုင်မှသာ Step 1 (0 index) သို့ ပြန်ဆင်းမည်
                self.send_telegram(f"✅ <b>ENSEMBLE WIN! Period: {short_period}</b>")
            else:
                reward = -3.5 - (self.current_step * 0.5)
                self.current_step += 1  # ❌ ရှုံးလျှင် အဆုံးမရှိ ဆက်တက်မည် (6x, 7x, 8x...)
                self.send_telegram(f"❌ <b>ENSEMBLE LOSS! Period: {short_period}</b>")
            
            self.update_q_table(self.last_state, predicted, reward)
            self.active_prediction = None

        self.window.append(current_result)
        
        if len(self.window) < 7:
            return

        recent_list = list(self.window)
        state_key = self.get_state_key()

        # Agent နှစ်ကောင်၏ Strategy ရလဒ်များကို ရယူခြင်း
        trend_pred, trend_desc = self.agent_trend_momentum(recent_list)
        revert_pred, revert_desc = self.agent_mean_reversion(recent_list, state_key)

        final_prediction = None
        market_regime = ""

        # Martingale Step မြင့်လာပါက ပိုမိုတင်းကျပ်သော စစ်ထုတ်မှုကို သုံးမည် (ဥပမာ Step 3 - 8x ကျော်လာလျှင်)
        if self.current_step >= 3:
            if trend_pred and trend_pred == revert_pred:
                final_prediction = trend_pred
                market_regime = f"Strict Strategy Safe Guard ({trend_desc})"
            else:
                final_prediction = None
                market_regime = "High Step Strategy Caution (Waiting)"
        else:
            if trend_pred and trend_pred == revert_pred:
                final_prediction = trend_pred
                market_regime = f"Strong Strategy Consensus ({trend_desc})"
            elif trend_pred and not revert_pred:
                final_prediction = trend_pred
                market_regime = f"Momentum Dominant ({trend_desc})"
            elif not trend_pred and revert_pred:
                final_prediction = revert_pred
                market_regime = f"Reversion Play ({revert_desc})"
            else:
                final_prediction = None
                market_regime = "Strategy Conflict (Waiting)"

        if final_prediction:
            self.last_state = state_key
            self.active_prediction = final_prediction
            current_multiplier = self.get_current_multiplier()
            
            msg = (
                f"👑 <b>PRO STRATEGY ENSEMBLE | Period: {short_period}</b>\n\n"
                f"📊 Market Regime: <b>{market_regime}</b>\n"
                f"🤖 Agent 1 (Momentum): <b>{trend_pred if trend_pred else 'Standby'}</b>\n"
                f"🤖 Agent 2 (Reversion): <b>{revert_pred if revert_pred else 'Standby'}</b>\n\n"
                f"🎯 <b>အတည်ပြု Signal:</b> <b>{final_prediction.upper()}</b>\n"
                f"💰 <b>Martingale Flow:</b> Step {self.current_step + 1} ({current_multiplier}x)"
            )
            self.send_telegram(msg)
        else:
            wait_msg = (
                f"⏳ <b>STRATEGY WAITING | Period: {short_period}</b>\n\n"
                f"📊 Status: <b>{market_regime}</b>\n"
                f"💬 <i>ပရိုဖက်ရှင်နယ် Strategy များ ချိန်ကိုက်နေဆဲဖြစ်ပါသည်...</i>"
            )
            self.send_telegram(wait_msg)

def run_bot():
    agent = DualAgentEnsemble()
    last_period = ""
    print("👑 Pro Strategy Dual-Agent Bot စတင် အလုပ်လုပ်နေပါပြီ...")
    
    url = "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList"
    headers = {
        "accept": "application/json, text/plain, *_**",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOiIxNzg3OTgxNTA5IiwibmJmIjoiMTc4Nzk4MTUwOSIsImV4cCI6IjE3ODc5ODMzMDkiLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL2V4cGlyYXRpb24iOiI4LzI5LzIwMjYgMTI6MzE6NDkgUE0iLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJBY2Nlc3NfVG9rZW4iLCJVc2VySWQiOiIxMDEyMjEzIiwiVXNlck5hbWUiOiI5NTk3NDA5MzkzNzAiLCJVc2VyUGhvdG8iOiI5IiwiTmlja05hbWUiOiJUaetsR3lpIiwiQW1vdW50IjoiODcuMzAiLCJJbnRlZ3JhbCI6IjAiLCJMb2dpbk1hcmsiOiJINSIsIkxvZ2luVGltZSI6IjgvMjkvMjAyNiAxMjowMTo0OSBQTSIsIjxvZ2luSVBBZGRyZXNzIjoiNDUuNDEuMTA0LjI0MCIsImRiTnVtYmVyIjoiMCIsIklzdmFsaWRhdG9yIjoiMCIsIktleUNvZGUiOiIzMjMzMiIsIlRva2VuVHlwZSI6IkFjY2Vzc19Ub2tlbiIsIlBob25lVHlwZSI6IjAiLCJVc2VyVHlwZSI6IjAiLCJVc2VyTmFtZ2UiOiIuIiwiaXNzIjoiand0SXNzdWVyIiwiYXVkIjoibG90dGVyeVRpY2tldCJ9.ZL0Y9gexUTCsKwWeZhCLAAw8AABEYJt0GnIzIviMG4g",
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
            response = requests.post(url, headers=headers, json, timeout=3)
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
