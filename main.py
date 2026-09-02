import requests
import time
import json
import os
import threading
from collections import deque

# ==========================================
# Telegram နဲ့ Supabase အချက်အလက်များ
# ==========================================
TELEGRAM_TOKEN = "8782457950:AAHbd-J29Y0fKhcBOHbSnn1d4z4vhiDQLKg" 
CHAT_ID = "-1003917249143"

SUPABASE_URL = "https://msgzacekhrvlqkqgjvly.supabase.co"
SUPABASE_KEY = "sb_publishable_bVJj1lqSAsIQ1kQ8Ae2vAQ_o3yCjDeA"
# ==========================================

class MultiAgentEnsemble:
    def __init__(self):
        self.window = deque(maxlen=10)
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
            res = requests.get(f"{SUPABASE_URL}/rest/v1/q_table?select=*", headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                q_dict = {}
                for row in data:
                    q_dict[row['state']] = row['actions']
                return q_dict
        except Exception as e:
            print(f"Error loading Q-Table: {e}")
        return {}

    def save_q_table(self, state, actions):
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        payload = {"state": state, "actions": actions}
        try:
            requests.post(f"{SUPABASE_URL}/rest/v1/q_table", headers=headers, json=payload, timeout=5)
        except Exception as e:
            print(f"Error saving Q-Table: {e}")

    def send_telegram(self, message):
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        try:
            res = requests.post(url, json=payload, timeout=5)
            print(f"Telegram sent status: {res.status_code}")
        except Exception as e:
            print(f"Telegram Error: {e}")

    def get_state_key(self):
        return ",".join(list(self.window)[-5:])

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

    # ==========================================
    # 🤖 6-Agent Committee တွက်ချက်မှုများ
    # ==========================================
    def agent_1_momentum(self, lst):
        if len(lst) >= 3 and lst[-1] == lst[-2] == lst[-3]:
            return lst[-1]
        return None

    def agent_2_reversion(self, lst):
        if len(lst) >= 4 and lst[-1] == lst[-2] == lst[-3] == lst[-4]:
            return "Small" if lst[-1] == "Big" else "Big"
        return None

    def agent_3_markov(self, lst):
        if len(lst) >= 5:
            if lst[-1] == lst[-2]:
                return "Small" if lst[-1] == "Big" else "Big"
            return lst[-1]
        return None

    def agent_4_qlearning(self, state_key):
        return self.get_q_action(state_key)

    def agent_5_frequency(self, lst):
        big_c = lst.count("Big")
        small_c = lst.count("Small")
        if big_c > small_c:
            return "Big"
        elif small_c > big_c:
            return "Small"
        return None

    def agent_6_streak(self, lst):
        if len(lst) >= 2:
            if lst[-1] != lst[-2]:
                return lst[-1]
        return None

    def get_committee_consensus(self, recent_list, state_key):
        votes = []
        v1 = self.agent_1_momentum(recent_list)
        if v1: votes.append(v1)
        v2 = self.agent_2_reversion(recent_list)
        if v2: votes.append(v2)
        v3 = self.agent_3_markov(recent_list)
        if v3: votes.append(v3)
        v4 = self.agent_4_qlearning(state_key)
        if v4: votes.append(v4)
        v5 = self.agent_5_frequency(recent_list)
        if v5: votes.append(v5)
        v6 = self.agent_6_streak(recent_list)
        if v6: votes.append(v6)

        if not votes:
            return None, "No Votes"

        big_votes = votes.count("Big")
        small_votes = votes.count("Small")

        if big_votes >= 4:
            return "Big", f"6-Agent Consensus ({big_votes}/6 Big)"
        elif small_votes >= 4:
            return "Small", f"6-Agent Consensus ({small_votes}/6 Small)"

        return None, f"Split Votes (Big: {big_votes}, Small: {small_votes}) - Skipped"

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
                self.send_telegram(f"✅ <b>AGENTS WIN! Period: {short_period}</b>")
            else:
                reward = -3.5 - (self.current_step * 0.5)
                self.total_losses += 1
                self.current_step += 1  
                self.send_telegram(f"❌ <b>AGENTS LOSS! Period: {short_period}</b>")
            
            self.update_q_table(self.last_state, predicted, reward)
            self.active_prediction = None

        self.window.append(current_result)
        
        if len(self.window) < 6:
            return

        recent_list = list(self.window)
        state_key = self.get_state_key()

        final_prediction, market_regime = self.get_committee_consensus(recent_list, state_key)

        if final_prediction:
            self.last_state = state_key
            self.active_prediction = final_prediction
            self.total_signals += 1  
            current_multiplier = self.get_current_multiplier()
            
            msg = (
                f"🤖 <b>6-AGENT COMMITTEE | Period: {short_period}</b>\n\n"
                f"🏛️ Regime: <b>{market_regime}</b>\n"
                f"🎯 <b>Signal:</b> <b>{final_prediction.upper()}</b>\n"
                f"💰 <b>Martingale:</b> Step {self.current_step + 1} ({current_multiplier}x)"
            )
            self.send_telegram(msg)

def poll_telegram_commands(agent):
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
        print("Telegram Webhook cleared successfully.")
    except Exception as e:
        print(f"Error clearing webhook: {e}")

    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=20"
            res = requests.get(url, timeout=25)
            if res.status_code == 200:
                data = res.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
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
                                f"📊 <b>6-AGENT PERFORMANCE REPORT</b>\n\n"
                                f"⚙️ State: <b>{'PAUSED 🛑' if agent.is_paused else 'RUNNING 🟢'}</b>\n"
                                f"🎯 Total Signals: <b>{agent.total_signals}</b>\n"
                                f"✅ Wins: <b>{agent.total_wins}</b> | ❌ Losses: <b>{agent.total_losses}</b>\n"
                                f"📈 <b>Win Rate: {win_rate:.2f}%</b>\n\n"
                                f"🚀 <b>Martingale Stats:</b>\n"
                                f"  • အမြင့်ဆုံး Level: <b>Step {agent.max_martingale_step_reached} ({2**(agent.max_martingale_step_reached-1) if agent.max_martingale_step_reached > 0 else 1}x)</b>\n"
                                f"  • လက်ရှိ Step: <b>Step {agent.current_step + 1} ({agent.get_current_multiplier()}x)</b>\n\n"
                                f"🏆 <b>Step အလိုက် နိုင်ခဲ့သည့်ပွဲများ:</b>\n"
                                f"{step_breakdown}"
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

def main():
    agent = MultiAgentEnsemble()
    
    # Telegram Command Listener Thread
    cmd_thread = threading.Thread(target=poll_telegram_commands, args=(agent,))
    cmd_thread.daemon = True
    cmd_thread.start()

    last_period = ""
    print("🤖 Pure 6-Agent Wingo Bot စတင် အလုပ်လုပ်နေပါပြီ...")
    
    url = "https://6lotteryapi.com/api/webapi/GetNoaverageEmerdList"
    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOiIxNzg3OTgxNTA5IiwibmJmIjoiMTc4Nzk4MTUwOSIsImV4cCI6IjE3ODc5ODMzMDkiLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL2V4cGlyYXRpb24iOiI4LzI5LzIwMjYgMTI6MzE2NDkgUE0iLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJBY2Nlc3NfVG9rZW4iLCJVc2VySWQiOiIxMDEyMjEzIiwiVXNlck5hbWUiOiI5NTk3NDA5MzkzNzAiLCJVc2VyUGhvdG8iOiI5IiwiTmlja05hbWUiOiJUaetsR3lpIiwiQW1vdW50IjoiODcuMzAiLCJJbnRlZ3JhbCI6IjAiLCJMb2dpbk1hcmsiOiJINSIsIkxvZ2luVGltZSI6IjgvMjkvMjAyNiAxMjowMTo0OSBQTSIsIjxvZ2luSVBBZGRyZXNzIjoiNDUuNDEuMTA0LjI0MCIsImRiTnVtYmVyIjoiMCIsIklzdmFsaWRhdG9yIjoiMCIsIktleUNvZGUiOiIzMjMzMiIsImRva2VuVHlwZSI6IjJBY2Nlc3NfVG9rZW4iLCJob25lVHlpZSI6IjAiLCJVc2VyVHlwZSI6IjAiLCJVc2VyTmFtZTIiOiIuIiwiaXNzIjoiand0SXNzdWVyIiwiYXVkIjoibG90dGVyeVRpY2tldCJ9.ZL0Y9gexUTCsKwWeZhCLAAw8AABEYJt0GnIzIviMG4g",
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
    main()
