# Deploy Circle on Oracle Cloud Always Free

Oracle Cloud Infrastructure (OCI) gives you a real Linux VM that stays on forever within free-tier limits. That means you can run Circle **as-is**: `uvicorn`, `circle.db`, and `refresh.json` on a normal disk.

This is different from Vercel: you get a persistent filesystem and a long-running process, so SQLite works.

## What you get (Always Free)

Rough free-tier allowance (can change; check Oracle’s docs):

- **Ampere A1** (ARM) compute: up to **4 OCPUs** and **24 GB RAM**, split across at most 4 VMs
- **Boot volume** storage (tens of GB free)
- A **public IP** so the internet can reach your API

A common small setup for one app:

- **1 OCPU**, **6 GB RAM**, Ubuntu 22.04/24.04 (aarch64)
- Open ports **22** (SSH) and **8000** (or 80/443 if you put Caddy/nginx in front)

You usually need a credit card to create the account. Always Free resources should stay **$0** if you only use free shapes and stay inside limits. Watch the billing page so you don’t accidentally create paid resources.

## Why this fits Circle

| Need | Oracle VM |
|------|-----------|
| `sqlite:///circle.db` | Yes — file on disk |
| Write `refresh.json` | Yes |
| `uvicorn app:app` | Yes — always-on process |
| Google OAuth secrets in `setup.py` | Copy onto the server (keep out of git) |

## Caveats

- **Capacity errors**: busy regions often return “Out of capacity” for Ampere. Retry later, try another AD/region, or create with fewer OCPUs/RAM.
- **ARM (aarch64)**: use Ubuntu ARM images. Pure-Python deps in this project are fine; avoid x86-only wheels.
- **Account / payment verification**: signup and first VM can take patience.
- **Security**: don’t leave SSH open to the world with a weak password. Prefer SSH keys. Don’t commit `setup.py` or `circle.db` if they have secrets/real user data.
- **HTTPS**: raw `:8000` is fine for testing; for real clients, put Caddy or nginx + Let’s Encrypt in front (or Cloudflare Tunnel).

---

## Setup steps

### 1. Create an Oracle Cloud account

1. Go to [https://cloud.oracle.com/](https://cloud.oracle.com/) and sign up for a Free Tier account.
2. Complete email/phone/payment verification.
3. Sign in to the **OCI Console**.

### 2. Create a free Ampere VM

1. In the Console: **Compute → Instances → Create instance**.
2. Name it (e.g. `circle`).
3. **Image**: Canonical Ubuntu 22.04 or 24.04 (**aarch64** / Ampere).
4. **Shape**: **Ampere** / `VM.Standard.A1.Flex`
   - Start with **1 OCPU**, **6 GB** memory (or less if capacity is tight).
5. **Networking**: use the default VCN/subnet with a **public IPv4** address.
6. **SSH keys**: upload your public key (or paste it). Save the private key locally.
7. Create the instance. Wait until state is **Running**.
8. Note the **Public IP** address.

If creation fails with capacity errors: change availability domain, reduce OCPU/RAM, try another home region, or retry over a few days.

### 3. Open the firewall in OCI

OCI blocks ports unless you open them on the **subnet security list** or **NSG**.

1. Find the instance → **Subnet** → **Security Lists** (or Network Security Group).
2. Add **Ingress** rules:

| Source | Protocol | Port | Purpose |
|--------|----------|------|---------|
| `0.0.0.0/0` | TCP | 22 | SSH |
| `0.0.0.0/0` | TCP | 8000 | Circle API (dev) |

For production later, prefer 80/443 only and reverse-proxy to uvicorn.

### 4. SSH into the VM

On your laptop:

```bash
ssh -i /path/to/your-private-key ubuntu@YOUR_PUBLIC_IP
```

Default user for Canonical Ubuntu images is usually `ubuntu`.

### 5. Install system packages

On the VM:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git ufw
```

Optional OS firewall (in addition to OCI security list):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 8000/tcp
sudo ufw enable
```

### 6. Get the Circle code onto the VM

**Option A — git clone** (if the repo is on GitHub/GitLab):

```bash
cd ~
git clone https://github.com/YOUR_USER/Circle.git
cd Circle
```

**Option B — copy from your laptop** (from your machine, not the VM):

```bash
rsync -avz -e "ssh -i /path/to/your-private-key" \
  --exclude '.venv' --exclude '.git' --exclude '__pycache__' --exclude '.mypy_cache' --exclude '.idea' \
  /home/matthew/Documents/Circle/ ubuntu@YOUR_PUBLIC_IP:~/Circle/
```

Then SSH back in and `cd ~/Circle`.

### 7. Copy secrets and the database

These are local / gitignored on your machine. Put them on the server:

From your laptop:

```bash
scp -i /path/to/your-private-key \
  /home/matthew/Documents/Circle/setup.py \
  /home/matthew/Documents/Circle/circle.db \
  ubuntu@YOUR_PUBLIC_IP:~/Circle/
```

On the VM, create an empty refresh-token store if missing:

```bash
cd ~/Circle
echo '[]' > refresh.json
```

`setup.py` holds Google OAuth secrets — keep the server locked down and never commit it.

### 8. Create a venv and install dependencies

```bash
cd ~/Circle
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 9. Smoke-test the API

```bash
cd ~/Circle
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
```

From your browser or laptop:

```text
http://YOUR_PUBLIC_IP:8000/
```

You should see the Circle index string. Hit Ctrl+C on the VM when done testing.

### 10. Run Circle under systemd (survive reboot)

Create a service file:

```bash
sudo nano /etc/systemd/system/circle.service
```

Paste (adjust paths if your home directory differs):

```ini
[Unit]
Description=Circle FastAPI
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Circle
Environment=PATH=/home/ubuntu/Circle/.venv/bin
ExecStart=/home/ubuntu/Circle/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable circle
sudo systemctl start circle
sudo systemctl status circle
```

Logs:

```bash
sudo journalctl -u circle -f
```

### 11. Point your client at the server

Use:

```text
http://YOUR_PUBLIC_IP:8000
```

Update Google OAuth **authorized origins / redirect URIs** if your frontend/backend URLs change.

---

## Optional: HTTPS with Caddy

For a real domain pointing at the VM’s public IP:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
# follow current Caddy install docs for Ubuntu, then:
```

Example Caddyfile reverse-proxy:

```caddy
api.yourdomain.com {
    reverse_proxy localhost:8000
}
```

Then open **80** and **443** in the OCI security list (and ufw), and you can leave uvicorn bound to `127.0.0.1:8000` instead of `0.0.0.0` if Caddy is on the same machine.

---

## Updating the app later

Circle runs as the systemd service `circle`. Updates are SSH + pull/sync + restart. `git pull` while the service is running is fine; Python already has the old code loaded. The **restart** is what picks up the new code.

### Update from git

SSH into the VM, then:

```bash
cd ~/Circle
git pull
source .venv/bin/activate
pip install -r requirements.txt   # only if deps changed
sudo systemctl restart circle
sudo systemctl status circle
```

If the repo was cloned over HTTPS and pulls ask for credentials, set up a deploy key or `gh auth` on the VM once so `git pull` is non-interactive.

### Useful service commands

```bash
sudo systemctl status circle      # is it up?
sudo systemctl restart circle     # apply code changes
sudo systemctl stop circle        # stop API
sudo systemctl start circle       # start again
sudo journalctl -u circle -f      # live logs
```

### If you used rsync instead of git

From your laptop (not the VM):

```bash
rsync -avz -e "ssh -i /path/to/your-private-key" \
  --exclude '.venv' --exclude '.git' --exclude '__pycache__' \
  --exclude 'circle.db' --exclude 'setup.py' --exclude 'refresh.json' \
  /home/matthew/Documents/Circle/ ubuntu@YOUR_PUBLIC_IP:~/Circle/
```

Then on the VM: `sudo systemctl restart circle`.

**Don’t** overwrite `setup.py`, `circle.db`, or `refresh.json` with a blind sync — those stay on the server.

### Back up the DB before risky changes

```bash
cp ~/Circle/circle.db ~/Circle/circle.db.bak-$(date +%F)
```

---

## Quick checklist

- [ ] OCI account created
- [ ] Ampere Ubuntu VM running with public IP
- [ ] Ingress TCP 22 and 8000 open
- [ ] SSH works with your key
- [ ] Code + `setup.py` + `circle.db` + `refresh.json` on the VM
- [ ] venv + `pip install -r requirements.txt`
- [ ] `systemctl` service running
- [ ] `http://PUBLIC_IP:8000/` responds

That’s the whole path: free always-on VM, persistent disk, Circle unchanged.

## SSH INTO MACHINE

go to folder Desktop / cirlce_ssh_keys

ssh -i 'ssh-key-2026-08-01(1).key' ubuntu@170.9.13.43

