"""Polite HTTP client: clear User-Agent, 1-2 s random delay between requests, robots.txt enforcement."""
import random
import re
import time
from urllib.parse import urlsplit

import requests

USER_AGENT = "terpene-scraper/1.0 (personal price comparison; low volume; honors robots.txt)"
MIN_DELAY, MAX_DELAY = 1.0, 2.0


class RobotsDisallowed(Exception):
    pass


class Robots:
    """Minimal robots.txt parser with Google-style wildcard (* and $) and longest-match semantics."""

    def __init__(self, text: str, agent: str = USER_AGENT):
        self.rules = []  # (allow: bool, regex, length)
        name = agent.split("/")[0].lower()
        groups, cur, seen_rule = [], None, False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = (x.strip() for x in line.split(":", 1))
            k = k.lower()
            if k == "user-agent":
                if cur is None or seen_rule:
                    cur, seen_rule = {"agents": [], "rules": []}, False
                    groups.append(cur)
                cur["agents"].append(v.lower())
            elif k in ("allow", "disallow") and cur is not None:
                seen_rule = True
                if v:
                    cur["rules"].append((k == "allow", v))
        chosen = [g for g in groups if any(a != "*" and a in name for a in g["agents"])] or \
                 [g for g in groups if "*" in g["agents"]]
        for g in chosen:
            for allow, pat in g["rules"]:
                rx = re.escape(pat).replace(r"\*", ".*")
                if rx.endswith(r"\$"):
                    rx = rx[:-2] + "$"
                self.rules.append((allow, re.compile(rx), len(pat)))

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        path = parts.path + ("?" + parts.query if parts.query else "")
        best = None  # (length, allow)
        for allow, rx, n in self.rules:
            if rx.match(path) and (best is None or n > best[0] or (n == best[0] and allow)):
                best = (n, allow)
        return True if best is None else best[1]


class PoliteSession:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        self._last = 0.0
        self._robots = {}
        self.requests_made = 0

    def robots_for(self, url: str) -> Robots:
        p = urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            self._wait()
            r = self.s.get(base + "/robots.txt", timeout=30)
            # Missing robots.txt (404) means no restrictions; other errors -> be conservative.
            if r.status_code == 404:
                text = ""
            else:
                r.raise_for_status()
                text = r.text
            self._robots[base] = Robots(text)
        return self._robots[base]

    def _wait(self):
        gap = time.monotonic() - self._last
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        if self._last and gap < delay:
            time.sleep(delay - gap)
        self._last = time.monotonic()

    def request(self, method: str, url: str, **kw):
        if not self.robots_for(url).allowed(url):
            raise RobotsDisallowed(url)
        self._wait()
        kw.setdefault("timeout", 60)
        for attempt in range(3):
            try:
                r = self.s.request(method, url, **kw)
                self.requests_made += 1
                if r.status_code in (429, 502, 503, 504) and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r
            except requests.ConnectionError:
                if attempt == 2:
                    raise
                time.sleep(5)
