# Deploying — share your laptop's platform with judges over the internet

> **Goal:** judges anywhere in the world can open a public URL in their browser and see your platform running on your laptop, for several days. The URL must stay the same across restarts and Wi-Fi drops.

This guide uses **ngrok with a reserved static domain** (free tier, stable URL) as the primary path. Cloudflare Tunnel is documented as an alternative for users who own a domain.

---

## Pick your tool

| Tool | URL stability | Free-tier limits | Setup |
|---|---|---|---|
| **ngrok + static domain** ✅ recommended | Same URL forever | 1 GB / month bandwidth, 1 endpoint | 5 min, no domain needed |
| **Cloudflare named tunnel** | Same URL forever | Unlimited bandwidth | Requires a domain on Cloudflare |
| Cloudflare quick tunnel (`trycloudflare.com`) | Random URL every restart | None | 30 sec — fine for one-off live demo, **not** for multi-day judging |
| ngrok no static domain | Changes every restart | 1 GB / month | Don't use — you'll have to message judges every time |

**This guide configures the ngrok static-domain path.** Cloudflare alternative is at the bottom.

---

## Before you tunnel — laptop prep

### Step 1 — Stop your laptop sleeping

Judges can't access the platform if the laptop sleeps. On Windows:

```
Settings → System → Power & Battery →
  • Screen and sleep:
    • When plugged in, turn off my screen after  →  Never
    • When plugged in, put my device to sleep    →  Never
```

If you need to close the lid: **Control Panel → Power Options → Choose what closing the lid does → Plugged in: Do nothing**.

### Step 2 — Make sure the stack is running

```powershell
cd c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ubid_platform
docker compose up -d
docker ps --format "{{.Names}}`t{{.Status}}"
```

You should see all 11 services as `Up`.

Verify locally:

```powershell
curl.exe http://localhost:8501          # Streamlit UI — should return HTML
curl.exe http://localhost:8000/health   # API — should return {"status":"ok"}
```

### Step 3 — Stay connected

- **Wi-Fi:** prefer a stable connection (home network, not a public café)
- **Cellular hotspot:** works as fallback if Wi-Fi drops
- ngrok auto-reconnects if your IP changes — same public URL keeps working

---

## ngrok with reserved static domain (recommended path)

### Step 1 — Sign up + reserve your free domain (one-time, ~2 min)

1. Sign up free at <https://dashboard.ngrok.com/signup> (Google / GitHub login works).
2. Open <https://dashboard.ngrok.com/get-started/your-authtoken> and copy your authtoken (long string starting with letters/digits).
3. Open <https://dashboard.ngrok.com/domains>. Click **+ New Domain** and accept (or pick) the suggested name. You get **1 free static domain** that looks like `dust-appendage-dreamy.ngrok-free.dev`. **This URL is yours forever** as long as the account stays active.

> The reserved domain persists across tunnel restarts, laptop reboots, and IP changes. You can hand judges the same link on day 1 and day 5.

### Step 2 — Download ngrok

| OS | Download |
|---|---|
| **Windows 64-bit** | <https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip> — unzip to `c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ngrok.exe` |
| **macOS** | `brew install ngrok/ngrok/ngrok` |
| **Linux x86_64** | `curl -O https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz` then `tar xzf ngrok-v3-stable-linux-amd64.tgz` |

Verify:

```powershell
c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ngrok.exe version
```

You should see `ngrok version 3.x.y`.

### Step 3 — Register your authtoken (one-time)

```powershell
c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ngrok.exe config add-authtoken <YOUR_AUTHTOKEN>
```

Output: `Authtoken saved to configuration file: C:\Users\<you>\AppData\Local\ngrok\ngrok.yml`

You only need to do this once per machine — the token persists in the config file.

### Step 4 — Start the tunnel

In a **PowerShell window** (don't close it — the tunnel runs as long as the process is alive):

```powershell
c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ngrok.exe http --url=dust-appendage-dreamy.ngrok-free.dev 8501
```

Replace `dust-appendage-dreamy.ngrok-free.dev` with **your own** reserved domain from Step 1.

After ~3 seconds you'll see output like:

```
t=2026-05-07T23:56:36 lvl=info msg="client session established"
t=2026-05-07T23:56:37 lvl=info msg="started tunnel" name=command_line addr=http://localhost:8501 url=https://dust-appendage-dreamy.ngrok-free.dev
```

That `https://dust-appendage-dreamy.ngrok-free.dev` URL is what you share with judges. Same URL every time you start the tunnel.

> **Don't close the window.** Closing it kills the tunnel. Minimise it instead.

### Step 5 — Test the URL yourself before sharing

Open the `https://*.ngrok-free.dev` URL in your phone's browser **over cellular** (turn Wi-Fi off) — that proves it really reaches your laptop from outside your network.

The Streamlit UI should load. Click a few tabs (Dashboard, Browse UBIDs, Sorting Mat) to confirm everything works through the tunnel.

### Step 6 — Share with judges

Send a short message:

> *Demo URL — Karnataka UBID Platform:*
> *<https://dust-appendage-dreamy.ngrok-free.dev>*
> *Live for the next several days. Best viewed on desktop. Source + setup steps in our GitHub repo.*

---

## Keeping it running for several days

### Auto-restart if it crashes

ngrok normally auto-reconnects if the network blips. But if the **process itself dies** (laptop reboot, accidental Ctrl-C), you need to relaunch.

Save this as `tunnel.ps1` next to `ngrok.exe` and run it once:

```powershell
while ($true) {
    Write-Host "[$(Get-Date)] Starting tunnel..." -ForegroundColor Green
    & "c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ngrok.exe" http --url=dust-appendage-dreamy.ngrok-free.dev 8501
    Write-Host "[$(Get-Date)] Tunnel exited. Restarting in 5s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
```

Each restart brings up the **same URL** because the static domain is reserved. Judges never need to be re-notified.

### Monitor the tunnel from anywhere

ngrok ships a local dashboard at <http://localhost:4040> — open it on your laptop to see live request log, request inspector, and tunnel status.

### Watch your bandwidth

Free tier is **1 GB / month**. The `localhost:4040` dashboard shows usage. To estimate: a typical Streamlit page load is ~5 MB; one judge clicking around for 10 min ≈ 50 MB. So 1 GB ≈ 20 judge-sessions. Plenty for the typical hackathon.

If you blow through it: upgrade to ngrok Personal ($8 / month), or fall back to the Cloudflare path below (no bandwidth limit).

---

## Optional — second tunnel for the API

ngrok free tier allows **1 simultaneous tunnel** per account. So you can tunnel either `:8501` (UI, recommended) **or** `:8000` (API) — not both.

If a judge wants to poke the OpenAPI docs, point them at the in-app Swagger embedding via the Streamlit UI, or screen-share the localhost API.

To temporarily tunnel the API instead, kill the UI tunnel and run:

```powershell
c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ngrok.exe http --url=dust-appendage-dreamy.ngrok-free.dev 8000
```

(Same domain, different upstream port.)

---

## Security considerations

| Consideration | Mitigation |
|---|---|
| **Anyone with the URL can use it** | The URL is unguessable but not authenticated. Share only with judges over private channels (email, hackathon Slack DM). |
| **Judges can mutate data** | They can approve/reject pairs and trigger retrains. Acceptable for the demo. Reset script below if anything goes sideways. |
| **Laptop is exposed** | ngrok forwards only port 8501. Other ports / files / processes on your laptop remain inaccessible. Safer than router port-forwarding. |
| **ngrok-free.dev splash page** | First visit shows a Cloudflare interstitial (5-second click-through). This is ngrok's anti-abuse check. Real users only see it once per day. |

### Reset state if a judge breaks something

```powershell
docker exec ubid_platform-ubid-api-1 python /app/scripts/wipe_data.py
# Then re-ingest the 5 source CSVs (see README.md "Quick start")
```

You'll be back to a clean state in 2 minutes.

---

## What can go wrong + how to fix

### "Tunnel session failed: account is limited to 1 simultaneous ngrok agent session"

You already have an ngrok process running somewhere. Find and kill it:

```powershell
Get-Process ngrok | Stop-Process -Force
```

Then restart the tunnel.

### "ERR_NGROK_3200" or "Tunnel not found"

Your reserved domain string in the command doesn't match the one in your dashboard. Double-check the exact spelling at <https://dashboard.ngrok.com/domains>.

### Judges see a Cloudflare browser-warning page that won't dismiss

ngrok-free domains show this once per day per visitor. They click "Visit Site" once, then it stops showing. To skip it programmatically (e.g. for API access via curl), add header `ngrok-skip-browser-warning: true`.

### "Failed to bind to port 8501" inside the container

Means the Streamlit container isn't running. Check:

```powershell
docker ps | findstr ubid-frontend
```

Should show `ubid_platform-ubid-frontend-1   Up   ...   0.0.0.0:8501->8501/tcp`. If not, `docker compose up -d ubid-frontend`.

### URL works for you but not for judges

- Some corporate networks block `*.ngrok-free.dev`. Ask the judge to try mobile data.
- Slow connection: Streamlit's first load is ~5 MB. Be patient on first paint.

### Tunnel keeps dropping

Network issue on your end. Use the auto-restart loop in the previous section. Wired Ethernet > Wi-Fi if available.

---

## Alternative — Cloudflare named tunnel (if you own a domain)

Use this path **only** if you already own a domain whose nameservers point to Cloudflare. Otherwise stick with ngrok above.

Setup, one time:

```powershell
# Download cloudflared (already in your repo at ubid-platform/cloudflared.exe)
.\cloudflared.exe tunnel login                              # opens browser, log into Cloudflare
.\cloudflared.exe tunnel create ubid-demo                   # creates a permanent tunnel
.\cloudflared.exe tunnel route dns ubid-demo ubid.yourdomain.com
```

Then to run:

```powershell
.\cloudflared.exe tunnel --url http://localhost:8501 run ubid-demo
```

Judges hit `https://ubid.yourdomain.com` — same URL forever, unlimited bandwidth, free.

If you don't own a domain, the **ngrok static domain above is the right choice**. Cloudflare's `trycloudflare.com` quick tunnel gives you a random URL each restart and is **not stable** for multi-day judging.

---

## Pre-demo checklist (run 30 min before sharing the URL)

```
☐ Laptop set to never sleep, lid-close=do-nothing
☐ Laptop plugged into power
☐ Wi-Fi connected and stable (test by pinging 8.8.8.8 for 60 sec)
☐ Docker Desktop running, all 11 services Up
☐ http://localhost:8501 loads in your own browser (sanity check)
☐ http://localhost:8000/health returns {"status":"ok"}
☐ Synthetic data ingested (Dashboard shows ~75 UBIDs)
☐ ngrok.exe in a stable folder, authtoken already configured
☐ Tunnel running (PowerShell window 1, or via tunnel.ps1 auto-restart loop)
☐ Reserved static URL copied + tested from your phone over cellular
☐ Email to judges drafted with the URL
☐ Recovery plan: know how to relaunch the tunnel if it dies
```

---

## TL;DR — minimum commands

One-time setup (after signup + domain reservation):

```powershell
c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ngrok.exe config add-authtoken <YOUR_AUTHTOKEN>
```

Every time you want the platform live:

```powershell
# 1. Stack up
cd c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ubid_platform
docker compose up -d

# 2. Tunnel up (keep window open)
c:\Users\Kunda\Desktop\Hackathon\ubid-platform\ngrok.exe http --url=dust-appendage-dreamy.ngrok-free.dev 8501
```

Then share `https://dust-appendage-dreamy.ngrok-free.dev` with judges. Same URL, every time.

---

## After the demo

Stop the tunnel by closing the PowerShell window or:

```powershell
Get-Process ngrok | Stop-Process
```

The reserved URL stays linked to your account but won't resolve to anything until you start the tunnel again. To reclaim local resources:

```powershell
docker compose down
```

To erase all data:

```powershell
docker compose down -v
```
