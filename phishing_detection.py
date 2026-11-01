"""
phishing_detection.py
Rule-based phishing URL scoring engine.
Checks the URL's text structure only - never visits the actual site.
"""
import re
from urllib.parse import urlparse
SHORTENERS = ["bit.ly","tinyurl.com","goo.gl","t.co","ow.ly","is.gd"]
SUSPICIOUS_WORDS = ["verify","login","secure","bank","account","update","confirm","signin","webscr","password"]
def score_url(url):
    score = 0
    reasons = []
    url_lower = url.lower().strip()
    if len(url) >= 75:
        score += 2
        reasons.append(f"URL is unusually long ({len(url)}characters)")
    ip_pattern = r"(\d{1,3}\.){3}\d{1,3}"
    if re.search(ip_pattern,url):
        score += 3
        reasons.append("URL uses an IP address instead of a domain name")
    if "@" in url:
        score += 3
        reasons.append("URL contains an '@' symbol (can hide the real destination)")
    if not url_lower.startswith("https://"):
        score += 2
        reasons.append("URL does not use HTTPS")
    try:
        domain = urlparse(url if "//" in url else "http://" + url).netloc
    except Exception:
        domain = url
    if domain.count("-") >= 2 or domain.count(".") >=4:
        score += 2
        reasons.append(f"Domain has an unusual number of hyphens/dots ({domain})")
    found_words = [w for w in SUSPICIOUS_WORDS if w in url_lower]
    if found_words:
        score += 2
        reasons.append(f"Contains suspicious keyword(s):{','.join(found_words)}")
    if any(short in url_lower for short in SHORTENERS):
        score += 2
        reasons.append("URL uses a known link shortener (real destination is hidden)")
    if score <= 3:
        level = "Safe"
    elif score <= 6:
        level = "Suspicious"
    else:
        level = "Likely Phishing"
    return score, level, reasons