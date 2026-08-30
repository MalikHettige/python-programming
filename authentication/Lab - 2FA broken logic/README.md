## Purpose

**Lab:** PortSwigger Web Security Academy — 2FA broken logic

This script was written specifically for the lab to demonstrate the **broken 2FA verification logic**.

### What it does

* Uses my authenticated lab session.
* Sets `verify=carlos` to target Carlos during the lab's verification step.
* Requests Carlos's 2FA page to trigger/generate a code.
* Concurrently tries all **4-digit MFA codes (`0000–9999`)**.
* Stops when the application returns `302`, indicating a successful 2FA verification.

### Why I wrote it

The lab's 2FA implementation allows the verification step to be attacked independently of the normal login flow. The script automates the repetitive 4-digit code attempts instead of testing them manually.

**Important:** This is a **lab-specific proof-of-concept**, not a general-purpose attack tool. The `LAB_URL` and session cookie are placeholders and must only be used with an authorized lab environment.

### Key pattern learned

> **When MFA verification has a small predictable code space, check whether rate limiting, attempt limits, or proper session/user binding prevent systematic guessing.**
