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
    <h2>📊 WINGO ADAPTIVE HYBRID BOT REPORT</h2>
    <p><b>Status:</b> {'PAUSED 🛑' if global_agent.is_paused else 'RUNNING 🟢'}</p>
    <p><b>Active Chat ID:</b> {CHAT_ID}</p>
    <p><b>Total Signals:</b> {global_agent.total_signals}</p>
    <p><b>Wins:</b> {global_agent.total_wins} | <b>Losses:</b> {global_agent.total_losses}</p>
    <p><b>Win Rate:</b> {win_rate:.2f}%</p>
    <p><b>Current Martingale Step:</b> Step {global_agent.current_step + 1} ({global_agent.get_current_multiplier()}x)</p>
    <p><b>Last Fetched Period:</b> {global_agent.last_period}</p>
    """

class AdaptiveHybridEngine:
    def __init__(self):
        global global_agent
        global_agent = self

        self.window = deque(maxlen=40)
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
        
        # နည်းလမ်းတစ်ခုချင်းစီ၏ အောင်မြင်မှု အမှတ်စာရင်း (Dynamic Weights)
        self.model_weights = {"Markov": 1.0, "Pattern": 1.0, "Streak": 1.0, "QLearning": 1.0}
        self.last_predictions_by_model = {}

    def get_current_multiplier(self):
        return 2 ** self.current_step

    def load_q_table(self):
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        try:
            res = requests.get(f"{SUPABASE_URL}/rest/v1/q_table?select=*", headers=headers, timeout=5)
            if res.status_code == 200:
                return {row['state']: row['actions'] for row in res.json()}
        except Exception as e:
            print(f"Load Q-Table Error: {e}", flush=True)
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
            print(f"Save Q-Table Error: {e}", flush=True)

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        try:
            res = requests.post(url, json=payload, timeout=5)
            print(f"Telegram Send Status: {res.status_code} - {res.text}", flush=True)
        except Exception as e:
            print(f"Telegram Send Error: {e}", flush=True)

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

    # ---------------------------------------------------------
    # 🧠 ADAPTIVE PREDICTION MODELS
    # ---------------------------------------------------------
    def markov_chain_predict(self, lst):
        if len(lst) < 4:
            return "Big"
        transitions = {"Big": {"Big": 0, "Small": 0}, "Small": {"Big": 0, "Small": 0}}
        lst_arr = list(lst)
        for i in range(len(lst_arr) - 1):
            curr = lst_arr[i]
            nxt = lst_arr[i+1]
            if curr in transitions and nxt in transitions[curr]:
                transitions[curr][nxt] += 1
        last_val = lst_arr[-1]
        big_c = transitions[last_val]["Big"]
        small_c = transitions[last_val]["Small"]
        if big_c == small_c:
            return last_val
        return "Big" if big_c > small_c else "Small"

    def deep_pattern_match(self, lst):
        lst_arr = list(lst)
        if len(lst_arr) < 8:
            return lst_arr[-1] if lst_arr else "Big"
        for length in range(5, 2, -1):
            pattern = lst_arr[-length:]
            matches = []
            for i in range(len(lst_arr) - length):
                sub = lst_arr[i:i+length]
                if sub == pattern and (i + length) < len(lst_arr):
                    matches.append(lst_arr[i+length])
            if matches:
                return max(set(matches), key=matches.count)
        return lst_arr[-1]

    def streak_trend_reversal(self, lst):
        lst_arr = list(lst)
        if len(lst_arr) < 5:
            return "Big"
        streak_count = 1
        for i in range(len(lst_arr)-2, -1, -1):
            if lst_arr[i] == lst_arr[-1]:
                streak_count += 1
            else:
                break
        if streak_count >= 3:
            return "Small" if lst_arr[-1] == "Big" else "Big"
        else:
            return lst_arr[-1]

    def q_momentum_predict(self, lst, state_key):
        q_act = self.get_q_action(state_key)
        recent = list(lst)[-3:] if len(lst) >= 3 else list(lst)
        mom = recent[-1] if recent else "Big"
        return q_act if q_act == mom else mom

    def check_market_volatility(self, lst):
        if len(lst) < 6:
            return False
        recent = list(lst)[-6:]
        flips = sum(1 for i in range(len(recent)-1) if recent[i] != recent[i+1])
        return flips >= 4

    def get_adaptive_consensus(self, recent_list, state_key):
        m1 = self.markov_chain_predict(recent_list)
        m2 = self.deep_pattern_match(recent_list)
        m3 = self.streak_trend_reversal(recent_list)
        m4 = self.q_momentum_predict(recent_list, state_key)

        # သိမ်းဆည်းထားသော Model အလိုက် Dynamic Weights များဖြင့် တွက်ချက်ခြင်း
        predictions = {"Markov": m1, "Pattern": m2, "Streak": m3, "QLearning": m4}
        self.last_predictions_by_model = predictions

        scores = {"Big": 0.0, "Small": 0.0}
        for model_name, pred in predictions.items():
            weight = self.model_weights.get(model_name, 1.0)
            scores[pred] += weight

        is_choppy = self.check_market_volatility(recent_list)
        filter_note = " ⚠️ (Choppy Market)" if is_choppy else ""

        big_score = scores["Big"]
        small_score = scores["Small"]

        if big_score > small_score:
            return "Big", f"Adaptive Weighted Majority ({big_score:.1f} Big){filter_note}"
        elif small_score > big_score:
            return "Small", f"Adaptive Weighted Majority ({small_score:.1f} Small){filter_note}"
        else:
            return m3, f"Adaptive Tie-Break, Fallback to {m3}{filter_note}"

    def analyze_round(self, period, current_result):
        self.last_period = str(period)
        if self.is_paused:
            return  

        short_period = "..." + str(period)[-3:] if len(str(period)) >= 3 else "..." + str(period)

        if self.active_prediction and self.last_state:
            predicted = self.active_prediction
            
            # Model တစ်ခုချင်းစီ၏ မှန်ကန်မှုကို စစ်ဆေးပြီး Weights များကို အလိုအလျောက် ချိန်ညှိခြင်း (Self-Learning)
            for model_name, pred in self.last_predictions_by_model.items():
                if pred.lower() == current_result.lower():
                    self.model_weights[model_name] = min(3.0, self.model_weights[model_name] + 0.15)
                else:
                    self.model_weights[model_name] = max(0.5, self.model_weights[model_name] - 0.15)

            if current_result.lower() == predicted.lower():
                reward = 5.0 if self.current_step == 0 else 4.0
                self.total_wins += 1
                self.current_step = 0  
                self.send_telegram(f"✅ <b>ADAPTIVE WIN! Period: {short_period}</b> (Result: {current_result})")
            else:
                reward = -4.5 - (self.current_step * 0.5)
                self.total_losses += 1
                self.current_step += 1  
                
                # Circuit Breaker: Martingale Step 9 ရောက်လာပါက အလွန်အမင်း မလောင်ကျွမ်းအောင် သတိပေးချက်ပို့မည်
                if self.current_step >= 9:
                    self.send_telegram(f"🚨 <b>HIGH RISK WARNING: Martingale Step {self.current_step + 1} Reached!</b>")

                self.send_telegram(f"❌ <b>ADAPTIVE LOSS! Period: {short_period}</b> (Result: {current_result})")
            
            self.update_q_table(self.last_state, predicted, reward)
            self.active_prediction = None

        self.window.append(current_result)
        if len(self.window) < 10:
            self.send_telegram(f"⏳ <b>Collecting Adaptive Data... Period: {short_period}</b> ({len(self.window)}/10)")
            return

        state_key = self.get_state_key()
        final_prediction, market_regime = self.get_adaptive_consensus(list(self.window), state_key)

        self.last_state = state_key
        self.active_prediction = final_prediction
        self.total_signals += 1  
        
        msg = (
            f"🤖 <b>ADAPTIVE HYBRID | Period: {short_period}</b>\n\n"
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
                                f"📊 <b>ADAPTIVE BOT REPORT</b>\n\n"
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
            print(f"Telegram Polling Error: {e}", flush=True)
        time.sleep(1)

def run_bot():
    print("🤖 Background Wingo Bot Thread Started (Adaptive Hybrid Engine)...", flush=True)
    agent = AdaptiveHybridEngine()
    
    threading.Thread(target=poll_telegram_commands, args=(agent,), daemon=True).start()

    last_period = ""
    url = "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList"
    auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOiIxNzg3OTgxNTA5IiwibmJmIjoiMTc4Nzk4MTUwOSIsImV4cCI6IjE3ODc5ODMzMDkiLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL2V4cGlyYXRpb24iOiI4LzI5LzIwMjYgMTI6MzE2NDkgUE0iLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJBY2Nlc3NfVG9rZW4iLCJVc2VySWQiOiIxMDEyMjEzIiwiVXNlck5hbWUiOiI5NTk3NDA5MzkzNzAiLCJVc2VyUGhvdG8iOiI5IiwiTmlja05hbWUiOiJUaetsR3lpIiwiQW1vdW50IjoiODcuMzAiLCJJbnRlZ3JhbCI6IjAiLCJMb2dpbk1hcmsiOiJINSIsImxvZ2luVGltZSI6IjgvMjkvMjAyNiAxMjowMTo0OSBQTSIsImxvZ2luSVBBZGRyZXNzIjoiNDUuNDEuMTA0LjI0MCIsImRiTnVtYmVyIjoiMCIsIklzdmFsaWRhdG9yIjoiMCIsIktleUNvZGUiOiIzMjMzMiIsImRva2VuVHypZSI6IjJBY2Nlc3NfVG9rZW4iLCJob25lVHlpZSI6IjAiLCJVc2VyVHlpZSI6IjAiLCJVc2VyTmFtZ2UiOiIuIiwiaXNzIjoiand0SXNzdWVyIiwiYXVkIjoibG90dGVyeVRpY2tldCJ9.ZL0Y9gexUTCsKwWeZhCLAAw8AABEYJt0GnIzIviMG4g"

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
            payload = {
                "pageSize": 10, 
                "pageNo": 1, 
                "typeId": 30, 
                "language": 7,
                "random": "036263f367384d418be07465793c8da8",
                "signature": "55F4FD150F15F090B943374F3C9BE78B",
                "timestamp": int(time.time())
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
                        print(f"API Success Sync - Round: {current_period} -> Result: {current_result}", flush=True)
                        agent.analyze_round(current_period, current_result)
            else:
                print(f"API Error Response: {response.text}", flush=True)
        except Exception as e:
            print(f"API Exception Error: {e}", flush=True)
        time.sleep(2)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
