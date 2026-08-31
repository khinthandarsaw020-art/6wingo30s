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
    return "Pro Trading Strategy Dual-Agent AI Bot (Fast Polling Stats) Running 24/7!"

class DualAgentEnsemble:
    def __init__(self):
        self.window = deque(maxlen=5)
        self.current_step = 0 
        self.active_prediction = None
        self.last_state = None
        self.is_paused = False  
        
        # 📊 Statistics Trackers
        self.total_signals = 0
        self.total_wins = 0
        self.total_losses = 0
        self.max_martingale_step_reached = 0  
        self.wins_per_step = {}               

        self.lr = 0.35
        self.q_table = self.load_q_table()

    def get_current_multiplier(self):
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

    def check_momentum_velocity(self, recent_list):
        if len(recent_list) >= 3:
            last_three = [str(x).capitalize() for x in recent_list[-3:]]
            if last_three == ["Big", "Big", "Big"]:
                return "Big", "Velocity Surge (Strong Streak)"
            elif last_three == ["Small", "Small", "Small"]:
                return "Small", "Velocity Surge (Strong Streak)"
        return None, None

    def get_momentum_score(self, recent_list):
        weights = [1.0, 1.4, 1.8, 2.3, 3.0]
        score_big = 0.0
        total_weight = sum(weights[-len(recent_list):])
        for i, val in enumerate(recent_list):
            w = weights[len(weights) - len(recent_list) + i]
            if str(val).capitalize() == "Big":
                score_big += w
        return score_big / total_weight

    def get_reversion_score(self, recent_list, state):
        if len(recent_list) >= 4:
            last_four = [str(x).capitalize() for x in recent_list[-4:]]
            if last_four.count("Big") == 4:
                return 0.15
            elif last_four.count("Small") == 4:
                return 0.85
        q_act = self.get_q_action(state)
        if q_act == "Big":
            return 0.65
        elif q_act == "Small":
            return 0.35
        return 0.50

    def analyze_round(self, period, current_result):
        if self.is_paused:
            return  

        short_period = "..." + str(period)[-3:] if len(str(period)) >= 3 else "..." + str(period)

        if self.active_prediction and self.last_state:
            predicted = self.active_prediction
            reward = 0
            
            current_level_num = self.current_step + 1
            if current_level_num > self.max_martingale_step_reached:
                self.max_martingale_step_reached = current_level_num

            if current_result.lower() == predicted.lower():
                reward = 4.0 if self.current_step == 0 else 3.0
                self.total_wins += 1
                
                step_key = f"Step {current_level_num} ({self.get_current_multiplier()}x)"
                self.wins_per_step[step_key] = self.wins_per_step.get(step_key, 0) + 1

                self.current_step = 0  
                self.send_telegram(f"✅ <b>ENSEMBLE WIN! Period: {short_period}</b>")
            else:
                reward = -3.5 - (self.current_step * 0.5)
                self.total_losses += 1
                self.current_step += 1  
                self.send_telegram(f"❌ <b>ENSEMBLE LOSS! Period: {short_period}</b>")
            
            self.update_q_table(self.last_state, predicted, reward)
            self.active_prediction = None

        self.window.append(current_result)
        
        if len(self.window) < 5:
            return

        recent_list = list(self.window)
        state_key = self.get_state_key()

        final_prediction = None
        market_regime = ""

        vel_pred, vel_desc = self.check_momentum_velocity(recent_list)
        if vel_pred and self.current_step < 3:
            final_prediction = vel_pred
            market_regime = f"Momentum Velocity ({vel_desc})"
        else:
            p_mom = self.get_momentum_score(recent_list)
            p_rev = self.get_reversion_score(recent_list, state_key)
            combined_score = (p_mom * 0.60) + (p_rev * 0.40)
            threshold = 0.58 if self.current_step >= 3 else 0.53

            if combined_score >= threshold:
                final_prediction = "Big"
                market_regime = f"Soft Voting Consensus ({combined_score*100:.0f}% Big Confidence)"
            elif combined_score <= (1.0 - threshold):
                final_prediction = "Small"
                market_regime = f"Soft Voting Consensus ({(1.0-combined_score)*100:.0f}% Small Confidence)"
            else:
                final_prediction = None
                market_regime = f"Neutral Score ({combined_score*100:.0f}%) - Balancing"

        if final_prediction:
            self.last_state = state_key
            self.active_prediction = final_prediction
            self.total_signals += 1  
            current_multiplier = self.get_current_multiplier()
            
            msg = (
                f"👑 <b>PRO STRATEGY ENSEMBLE | Period: {short_period}</b>\n\n"
                f"📊 Market Regime: <b>{market_regime}</b>\n"
                f"🎯 <b>အတည်ပြု Signal:</b> <b>{final_prediction.upper()}</b>\n"
                f"💰 <b>Martingale Flow:</b> Step {self.current_step + 1} ({current_multiplier}x)"
            )
            self.send_telegram(msg)
        else:
            wait_msg = (
                f"⏳ <b>STRATEGY WAITING | Period: {short_period}</b>\n\n"
                f"📊 Status: <b>{market_regime}</b>\n"
                f"💬 <i>အမှတ်ချိန်ကိုက်နေဆဲဖြစ်ပါသည်...</i>"
            )
            self.send_telegram(wait_msg)

# 🛠️ ပိုမိုမြန်ဆန် တိကျသော Telegram Command Polling (Error Handling ပါဝင်သည်)
def poll_telegram_commands(agent):
    last_update_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=10"
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                data = res.json()
                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    message = update.get("message", {})
                    text = message.get("text", "").strip().lower()
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    
                    if chat_id == CHAT_ID:
                        if text == "/status":
                            total_resolved = agent.total_wins + agent.total_losses
                            win_rate = (agent.total_wins / total_resolved * 100) if total_resolved > 0 else 0.0
                            
                            step_breakdown = ""
                            if agent.wins_per_step:
                                for s_name, s_count in sorted(agent.wins_per_step.items()):
                                    step_breakdown += f"  • {s_name}: <b>{s_count} ပွဲ နိုင်</b>\n"
                            else:
                                step_breakdown = "  • မရှိသေးပါ\n"

                            status_msg = (
                                f"📊 <b>ADVANCED BOT PERFORMANCE REPORT</b>\n\n"
                                f"⚙️ State: <b>{'PAUSED 🛑' if agent.is_paused else 'RUNNING 🟢'}</b>\n"
                                f"🎯 Total Signals Issued: <b>{agent.total_signals}</b>\n"
                                f"✅ Total Wins: <b>{agent.total_wins}</b> | ❌ Total Losses: <b>{agent.total_losses}</b>\n"
                                f"📈 <b>Win Rate: {win_rate:.2f}%</b>\n\n"
                                f"🚀 <b>Martingale Statistics:</b>\n"
                                f"  • အမြင့်ဆုံးရောက်ခဲ့သော Level: <b>Step {agent.max_martingale_step_reached} ({2**(agent.max_martingale_step_reached-1) if agent.max_martingale_step_reached > 0 else 1}x)</b>\n"
                                f"  • လက်ရှိ Martingale Flow: <b>Step {agent.current_step + 1} ({agent.get_current_multiplier()}x)</b>\n\n"
                                f"🏆 <b>Step တစ်ခုချင်းစီအလိုက် နိုင်ခဲ့သည့်ပွဲများ:</b>\n"
                                f"{step_breakdown}\n"
                                f"📋 Window History: <code>{list(agent.window)}</code>"
                            )
                            agent.send_telegram(status_msg)
                        elif text == "/pause":
                            agent.is_paused = True
                            agent.send_telegram("🛑 <b>Bot ကို ခဏရပ်နားလိုက်ပါပြီ (/pause)။</b>")
                        elif text == "/resume":
                            agent.is_paused = False
                            agent.send_telegram("🟢 <b>Bot ကို ပြန်လည်စတင်လိုက်ပါပြီ (/resume)။</b>")
        except Exception as e:
            pass
        time.sleep(1)

def run_bot():
    agent = DualAgentEnsemble()
    
    cmd_thread = threading.Thread(target=poll_telegram_commands, args=(agent,))
    cmd_thread.daemon = True
    cmd_thread.start()

    last_period = ""
    print("👑 Pro Strategy Dual-Agent Bot (Stats Tracker) စတင် အလုပ်လုပ်နေပါပြီ...")
    
    url = "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList"
    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOiIxNzg3OTgxNTA5IiwibmJmIjoiMTc4Nzk4MTUwOSIsImV4cCI6IjE3ODc5ODMzMDkiLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL2V4cGlyYXRpb24iOiI4LzI5LzIwMjYgMTI6MzE6NDkgUE0iLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL2JvbGUiOiJBY2Nlc3NfVG9rZW4iLCJVc2VySWQiOiIxMDEyMjEzIiwiVXNlck5hbWUiOiI5NTk3NDA5MzkzNzAiLCJVc2VyUGhvdG8iOiI5IiwiTmlja05hbWUiOiJUaetsR3lpIiwiQW1vdW50IjoiODcuMzAiLCJJbnRlZ3JhbCI6IjAiLCJMb2dpbk1hcmsiOiJINSIsIkxvZ2luVGltZSI6IjgvMjkvMjAyNiAxMjowMTo0OSBQTSIsIjxvZ2luSVBBZGRyZXNzIjoiNDUuNDEuMTA0LjI0MCIsImRiTnVtYmVyIjoiMCIsIklzdmFsaWRhdG9yIjoiMCIsIktleUNvZGUiOiIzMjMzMiIsIlRva2VuVHlwZSI6IjJBY2Nlc3NfVG9rZW4iLCJob25lVHlpZSI6IjAiLCJVc2VyVHlwZSI6IjAiLCJVc2VyTmFtZTIiOiIuIiwiaXNzIjoiand0SXNzdWVyIiwiYXVkIjoibG90dGVyeVRpY2tldCJ9.ZL0Y9gexUTCsKwWeZhCLAAw8AABEYJt0GnIzIviMG4g",
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
