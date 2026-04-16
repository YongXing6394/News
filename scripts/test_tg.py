import os
import requests

def test_tg():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ 错误: 环境变量 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 为空！")
        return

    print(f">> 正在尝试向 Chat ID: {chat_id} 发送测试消息...")
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": "✅ GitHub Actions 联通性测试成功！\n这是一条来自测试脚本的消息。",
        "parse_mode": "Markdown"
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print(">> [OK] 消息发送成功！你的 Secrets 配置和网络路径都是通的。")
    except Exception as e:
        print(f">> [ERROR] 发送失败！")
        print(f">> 错误详情: {e}")
        if resp := getattr(e, 'response', None):
            print(f">> 服务器返回内容: {resp.text}")
        exit(1) # 让 GitHub Actions 标记为失败

if __name__ == "__main__":
    test_tg()
