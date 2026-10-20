import os, json, socket, subprocess, shutil, tempfile, time, random, base64
import urllib.request
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor

DL = os.path.expanduser("~/storage/downloads")
INP = os.path.join(DL, "config baray test.txt")
OUT = os.path.join(DL, "configay salem.txt")

def fetch_sub(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore").strip()
        if "vless://" not in data:
            data = "".join(data.split())
            data = base64.b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "ignore")
        return [l.strip() for l in data.splitlines() if l.strip().startswith("vless://")]
    except Exception as e:
        print("sub failed:", url[:50], e)
        return []

def parse(link):
    u = urlparse(link)
    return u, {k: v[0] for k, v in parse_qs(u.query).items()}

def tcp_ok(link):
    try:
        u, _ = parse(link)
        socket.create_connection((u.hostname, u.port), timeout=4).close()
        return True
    except Exception:
        return False

def build(link, port):
    u, q = parse(link)
    net, sec = q.get("type", "tcp"), q.get("security", "none")
    ss = {"network": net, "security": sec}
    if sec == "tls":
        ss["tlsSettings"] = {"serverName": q.get("sni", u.hostname),
                             "fingerprint": q.get("fp", "chrome"),
                             "allowInsecure": True}
    elif sec == "reality":
        ss["realitySettings"] = {"serverName": q.get("sni", ""),
                                 "fingerprint": q.get("fp", "chrome"),
                                 "publicKey": q.get("pbk", ""),
                                 "shortId": q.get("sid", ""),
                                 "spiderX": q.get("spx", "")}
    if net == "ws":
        ss["wsSettings"] = {"path": unquote(q.get("path", "/")),
                            "headers": {"Host": q.get("host", u.hostname)}}
    elif net == "grpc":
        ss["grpcSettings"] = {"serviceName": q.get("serviceName", "")}
    user = {"id": u.username, "encryption": "none"}
    if q.get("flow"):
        user["flow"] = q["flow"]
    return {
        "inbounds": [{"port": port, "listen": "127.0.0.1",
                      "protocol": "socks", "settings": {"udp": False}}],
        "outbounds": [{"protocol": "vless",
                       "settings": {"vnext": [{"address": u.hostname,
                                               "port": u.port,
                                               "users": [user]}]},
                       "streamSettings": ss}],
    }

def xray_ok(link):
    port = random.randint(20000, 60000)
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(build(link, port), f)
    f.close()
    p = subprocess.Popen(["xray", "run", "-c", f.name],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        r = subprocess.run(
            ["curl", "-s", "-m", "8", "-o", "/dev/null", "-w", "%{http_code}",
             "-x", f"socks5h://127.0.0.1:{port}",
             "https://www.gstatic.com/generate_204"],
            capture_output=True, text=True)
        return r.stdout.strip() == "204"
    except Exception:
        return False
    finally:
        p.kill()
        os.unlink(f.name)

# ---- ورودی ----
entered = input("لینک ساب رو وارد کن و اینتر بزن: ").split()
lines = entered
if not lines:
    if os.path.exists(INP):
        lines = [l.strip() for l in open(INP, encoding="utf-8") if l.strip()]
    else:
        print("لینکی وارد نشد و فایل config baray test هم پیدا نشد.")
        raise SystemExit

links = []
for line in lines:
    if line.startswith("vless://"):
        links.append(line)
    elif line.startswith("http"):
        got = fetch_sub(line)
        print(len(got), "configs from", line[:50])
        links += got
links = list(dict.fromkeys(links))
print(len(links), "configs total")

with ThreadPoolExecutor(50) as ex:
    alive = [l for l, ok in zip(links, ex.map(tcp_ok, links)) if ok]
print(len(alive), "passed TCP")

if shutil.which("xray") and shutil.which("curl"):
    with ThreadPoolExecutor(8) as ex:
        good = [l for l, ok in zip(alive, ex.map(xray_ok, alive)) if ok]
else:
    print("xray not found, TCP only")
    good = alive

open(OUT, "w", encoding="utf-8").write("\n".join(good))
print(len(good), "saved to:", OUT)
