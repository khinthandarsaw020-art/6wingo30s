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
CHAT_ID = "-1004341746467"

SUPABASE_URL = "https://msgzacekhrvlqkqgjvly.supabase.co"
SUPABASE_KEY = "sb_publishable_bVJj1lqSAsIQ1kQ8Ae2vAQ_o3yCjDeA"
# ==========================================

app = Flask(__name__)
global_agent = None

@app.route('/')
def home():
    global global_agent
    if not global_agent:
        return "<h3>🤖 Bot is starting...</h3>"
    
    total_resolved = global_agent.total_wins + global_agent.total_losses
    win_rate = (global_agent.total_wins / total_resolved * 100) if total_resolved > 0 else 0.0
    
    return f"""
    <h2>📊 6-AGENT TRADING BOT REPORT (WORKING API SYNC)</h2>
    <p><b>Status:</b> {'PAUSED 🛑' if global_agent.is_paused else 'RUNNING 🟢'}</p>
    <p><b>Active Chat ID:</b> {CHAT_ID}</p>
    <p><b>Total Signals:</b> {global_agent.total_signals}</p>
    <p><b>Wins:</b> {global_agent.total_wins} | <b>Losses:</b> {global_agent.total_losses}</p>
    <p><b>Win Rate:</b> {win_rate:.2f}%</p>
    <p><b>Current Martingale Step:</b> Step {global_agent.current_step + 1} ({global_agent.get_current_multiplier()}x)</p>
    <p><b>Last Fetched Period:</b> {global_agent.last_period}</p>
    """

class MultiAgentEnsemble:
    def __init__(self):
        global global_agent
        global_agent = self

        self.window = deque(maxlen=20)
        self.current_step = 0 
        self.active_prediction = None
        self.last_state = None
        self.is_paused = False  
        self.last_period = "None"
        
        self.total_signals = 0
        self.total_wins = 0
        self.total_losses = 0

        self.lr = 0.40
        self.q_table = self.load_q_table()

    def get_current_multiplier(self):
        return 2 ** self.current_step

    def load_q_table(self):
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        try:
            res = requests.get(f"{SUPABASE_URL}/rest/v1/q_table?select=*", headers=headers, timeout=5)
            if res.status_code == 200:
                return {row['state']: row['actions'] for row in res.json()}
        except Exception as e:
            pass
        return {}

    def save_q_table(self, state, actions):
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        try:
            requests.post(f"{SUPABASE_URL}/rest/v1/q_table", headers=headers, json={"state": state, "actions": actions}, timeout=5)
        except Exception as e:
            pass

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        try:
            res = requests.post(url, json=payload, timeout=5)
            print(f"Telegram Send Status: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Telegram Send Error: {e}")

    def get_state_key(self):
        if len(self.window) < 5:
            return "Big,Big,Big,Big,Big"
        return ",".join(list(self.window)[-5:])

    def get_q_action(self, state):
        if state not in self.q_table:
            self.q_table[state] = {"Big": 1.5, "Small": 1.5}
        actions = self.q_table[state]
        return "Big" if actions["Big"] >= actions["Small"] else "Small"

    def update_q_table(self, state, action, reward):
        if state not in self.q_table:
            self.q_table[state] = {"Big": 1.5, "Small": 1.5}
        old_q = self.q_table[state][action]
        self.q_table[state][action] = old_q + self.lr * (reward - old_q)
        self.save_q_table(state, self.q_table[state])

    def agent_1_micro_momentum(self, lst):
        recent = list(lst)[-3:]
        return recent[-1] if recent else "Big"

    def agent_2_macro_trend(self, lst):
        if len(lst) >= 10:
            macro = list(lst)[-15:]
            big_c = macro.count("Big")
            small_c = macro.count("Small")
            return "Big" if big_c >= small_c else "Small"
        return lst[-1] if lst else "Big"

    def agent_3_pattern_ml(self, lst):
        if len(lst) >= 6:
            p = list(lst)[-4:]
            matches = [lst[i+4] for i in range(len(lst)-4) if list(lst)[i:i+4] == p]
            if matches:
                return max(set(matches), key=matches.count)
        return lst[-1] if lst else "Big"

    def agent_4_qlearning(self, state_key):
        return self.get_q_action(state_key)

    def agent_5_frequency(self, lst):
        if not lst:
            return "Big"
        sub = list(lst)[-8:]
        return "Big" if sub.count("Big") >= sub.count("Small") else "Small"

    def agent_6_reversal(self, lst):
        if len(lst) >= 3 and lst[-1] == lst[-2] == lst[-3]:
            return "Small" if lst[-1] == "Big" else "Big"
        return "Small" if (lst and lst[-1] == "Big") else "Big"

    def check_market_volatility(self, lst):
        if len(lst) < 6:
            return False
        recent = list(lst)[-6:]
        flips = sum(1 for i in range(len(recent)-1) if recent[i] != recent[i+1])
        return flips >= 4

    def get_committee_consensus(self, recent_list, state_key):
        votes = [
            self.agent_1_micro_momentum(recent_list),
            self.agent_2_macro_trend(recent_list),
            self.agent_3_pattern_ml(recent_list),
            self.agent_4_qlearning(state_key),
            self.agent_5_frequency(recent_list),
            self.agent_6_reversal(recent_list)
        ]

        big_votes = votes.count("Big")
        small_votes = votes.count("Small")
        is_choppy = self.check_market_volatility(recent_list)
        filter_note = " ⚠️ (Choppy Market)" if is_choppy else ""

        if big_votes > small_votes:
            return "Big", f"Advanced Majority ({big_votes}/6 Big){filter_note}"
        elif small_votes > big_votes:
            return "Small", f"Advanced Majority ({small_votes}/6 Small){filter_note}"
        else:
            fallback = recent_list[-1] if recent_list else "Big"
            return fallback, f"Tie (3-3), Fallback to {fallback}{filter_note}"

    def analyze_round(self, period, current_result):
        self.last_period = str(period)
        if self.is_paused:
            return  

        short_period = "..." + str(period)[-3:] if len(str(period)) >= 3 else "..." + str(period)

        if self.active_prediction and self.last_state:
            predicted = self.active_prediction
            if current_result.lower() == predicted.lower():
                reward = 5.0 if self.current_step == 0 else 4.0
                self.total_wins += 1
                self.current_step = 0  
                self.send_telegram(f"✅ <b>AGENTS WIN! Period: {short_period}</b> (Result: {current_result})")
            else:
                reward = -4.5 - (self.current_step * 0.5)
                self.total_losses += 1
                self.current_step += 1  
                self.send_telegram(f"❌ <b>AGENTS LOSS! Period: {short_period}</b> (Result: {current_result})")
            
            self.update_q_table(self.last_state, predicted, reward)
            self.active_prediction = None

        self.window.append(current_result)
        if len(self.window) < 10:
            self.send_telegram(f"⏳ <b>Collecting Data... Period: {short_period}</b> ({len(self.window)}/10)")
            return

        state_key = self.get_state_key()
        final_prediction, market_regime = self.get_committee_consensus(list(self.window), state_key)

        self.last_state = state_key
        self.active_prediction = final_prediction
        self.total_signals += 1  
        
        msg = (
            f"🤖 <b>ADVANCED COMMITTEE | Period: {short_period}</b>\n\n"
            f"🏛️ Regime: <b>{market_regime}</b>\n"
            f"🎯 <b>Signal:</b> <b>{final_prediction.upper()}</b>\n"
            f"💰 <b>Martingale:</b> Step {self.current_step + 1} ({self.get_current_multiplier()}x)"
        )
        self.send_telegram(msg)

def poll_telegram_commands(agent):
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except:
        pass

    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=20"
            res = requests.get(url, timeout=25)
            if res.status_code == 200:
                for update in res.json().get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {}) or update.get("edited_message", {})
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    text = message.get("text", "").strip().lower()
                    
                    if chat_id == CHAT_ID:
                        if text == "/status":
                            total_resolved = agent.total_wins + agent.total_losses
                            win_rate = (agent.total_wins / total_resolved * 100) if total_resolved > 0 else 0.0
                            status_msg = (
                                f"📊 <b>ADVANCED BOT PERFORMANCE REPORT</b>\n\n"
                                f"⚙️ State: <b>{'PAUSED 🛑' if agent.is_paused else 'RUNNING 🟢'}</b>\n"
                                f"🎯 Total Signals: <b>{agent.total_signals}</b>\n"
                                f"✅ Wins: <b>{agent.total_wins}</b> | ❌ Losses: <b>{agent.total_losses}</b>\n"
                                f"📈 <b>Win Rate: {win_rate:.2f}%</b>"
                            )
                            agent.send_telegram(status_msg)
                        elif text == "/pause":
                            agent.is_paused = True
                            agent.send_telegram("🛑 <b>Bot Paused.</b>")
                        elif text == "/resume":
                            agent.is_paused = False
                            agent.send_telegram("🟢 <b>Bot Resumed.</b>")
        except Exception as e:
            print(f"Telegram Polling Error: {e}")
        time.sleep(1)

def run_bot():
    print("🤖 Background Wingo Bot Thread Started (Working API Sync)...")
    agent = MultiAgentEnsemble()
    
    threading.Thread(target=poll_telegram_commands, args=(agent,), daemon=True).start()

    last_period = ""
    url = "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList"
    
    auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOiIxNzg3OTgxNTA5IiwibmJmIjoiMTc4Nzk4MTUwOSIsImV4cCI6IjE3ODc5ODMzMDkiLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL2V4cGlyYXRpb24iOiI4LzI5LzIwMjYgMTI6MzE2NDkgUE0iLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJBY2Nlc3NfVG9rZW4iLCJVc2VySWQiOiIxMDEyMjEzIiwiVXNlck5hbWUiOiI5NTk3NDA5MzkzNzAiLCJVc2VyUGhvdG8iOiI5IiwiTmlja05hbWUiOiJUaetsR3lpIiwiQW1vdW50IjoiODcuMzAiLCJJbnRlZ3JhbCI6IjAiLCJMb2dpbk1hcmsiOiJINSIsIkxvZ2luVGltZSI6IjgvMjkvMjAyNiAxMjowMTo0OSBQTSIsIjxvZ2luSVBBZGRyZXNzIjoiNDUuNDEuMTA0LjI0MCIsImRiTnVtYmVyIjoiMCIsIklzdmFsaWRhdG9yIjoiMCIsIktleUNvZGUiOiIzMjMzMiIsImRva2VuVHypZSI6IjJBY2Nlc3NfVG9rZW4i লিওsIjAwIiwiVXNlclR5aWUiOiIwIiwiVXNlck5hbWdlIjoiLiIsImlzcyI6Imp3dElzc3VlciIsImF1ZCI6ImxvdHRlcnl0aWNrZXQifQ.ZL0Y9gexUTCsKwWeZhCLAAw8AABEYJt0GnIzIviMG4g"

    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": f"Bearer {auth_token}",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://6win598.com",
        "referer": "https://6win598.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    while True:
        try:
            # တခြားအလုပ်လုပ်နေတဲ့ Bot ကဲ့သို့ တိကျသော Payload ပုံစံ
            payload = {
                "pageSize": 10, 
                "pageNo": 1, 
                "typeId": 30, 
                "language": 7,
                "random": "036263f367384d418be07465793c8da8",
                "signature": "55F4FD150F15F090B943374F3C9BE78B",
                "timestamp": int(time.time() * 1000)
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
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
                        print(f"API Success Sync - Round: {current_period} -> Result: {current_result}")
                        agent.analyze_round(current_period, current_result)
            else:
                print(f"API Sync Error Code: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"API Sync Exception: {e}")
        time.sleep(1.5)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
