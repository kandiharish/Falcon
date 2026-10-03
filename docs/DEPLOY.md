# Deploying FALCON for $0

FALCON runs as five containers: web (Caddy, HTTPS), api, worker, db (PostgreSQL), plus
optional ollama (local AI). Anything that runs Docker can host it. These are the realistic
free options, as of October 2026. Free offers change, so check the current terms before
signing up.

| Option | Cost | Good for | Limits |
|---|---|---|---|
| **A. Oracle Cloud "Always Free" VM** (recommended) | $0 | A real, always-on demo with HTTPS, including the AI | Needs a card for identity verification at sign-up (not charged on Always Free). ARM machine: up to 4 cores and 24 GB RAM, enough for qwen3:8b. |
| B. Your own PC + Cloudflare *quick tunnel* | $0, no account | Showing FALCON to someone for an hour | Random temporary address; only up while your PC is on. |
| C. Your own PC on your network | $0 | Learning, development | Not reachable from outside. |

> FALCON contains only fictional demo data. For **real** evidence you would also need legal
> approval, proper hosting agreements, encryption at rest, backups off-site and a security review.

---

## The production stack (same for every option)

```
 Internet ──HTTPS:443──► web (Caddy) ── automatic certificates, security headers, the React app
                           └─ /api ──► api (FastAPI) ─┐
                                       worker          ├─► db (PostgreSQL; not reachable from outside)
                                       migrate (once) ─┘
                                       ollama (optional, --profile ai)
```

```sh
git clone https://github.com/kandiharish/Falcon.git && cd Falcon
cp deploy/.env.production.example deploy/.env.production
# edit deploy/.env.production: FALCON_SITE, POSTGRES_PASSWORD, FALCON_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"     # run twice for the two secrets

docker compose -f docker-compose.prod.yml --env-file deploy/.env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file deploy/.env.production run --rm api \
    python -m app.scripts.create_admin                             # your first administrator
```

FALCON **refuses to start** with unsafe settings (insecure cookies, a short secret key, a weak
database password, demo accounts). That is deliberate. Read the message, fix the setting,
start again.

Local AI (optional, about 8 GB of RAM):
```sh
docker compose -f docker-compose.prod.yml --env-file deploy/.env.production --profile ai up -d
docker compose -f docker-compose.prod.yml --env-file deploy/.env.production exec ollama ollama pull qwen3:8b
docker compose -f docker-compose.prod.yml --env-file deploy/.env.production exec ollama ollama pull all-minilm
```

---

## Option A: Oracle Cloud Always Free, step by step

1. **Sign up** at cloud.oracle.com (choose your home region carefully; it can't be changed).
2. **Create a VM**: Compute → Instances → Create.
   - Image: *Ubuntu 24.04*; Shape: *Ampere VM.Standard.A1.Flex*, 4 OCPU / 24 GB.
   - Add your SSH public key. Keep the default 50 GB boot volume or raise it within the free 200 GB.
3. **Open the web ports**: Networking → your VCN → Security list → add ingress rules for TCP **80**
   and **443** from 0.0.0.0/0. On the VM itself, Ubuntu's firewall must allow them too:
   ```sh
   sudo iptables -I INPUT 6 -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```
4. **A free domain name**: create a subdomain at duckdns.org (e.g. `myfalcon.duckdns.org`) and point
   it to the VM's public IP.
5. **Install Docker** on the VM:
   ```sh
   curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER   # log out and in
   ```
6. **Deploy** with the commands in "The production stack" above, using
   `FALCON_SITE=myfalcon.duckdns.org`. Caddy gets a Let's Encrypt certificate automatically on
   the first visit. Open `https://myfalcon.duckdns.org`.
7. **Backups**: `./deploy/backup.sh` daily (cron), then copy `backups/` off the VM (e.g. to
   Oracle's free Object Storage, or your PC with `scp`).
8. **Updates**: `git pull && docker compose -f docker-compose.prod.yml --env-file deploy/.env.production up -d --build`.
   The `migrate` service upgrades the database before the API starts.

## Option B: a temporary public link from your PC

With the production stack running locally (`FALCON_SITE=localhost`, ports 8080/8443):
```sh
cloudflared tunnel --url https://localhost:8443 --no-tls-verify
```
This prints a random `https://….trycloudflare.com` address that works until you stop it. It
needs no account and opens no ports. Share it only for a short demo.

---

## After deploying: checklist

- [ ] Signed in as the administrator, **turned on MFA**, created real user accounts
- [ ] `https://` works and `http://` redirects to it (Caddy does both)
- [ ] `deploy/.env.production` is only on the server (never committed; git ignores it)
- [ ] A backup was made **and restored once** to prove it works
- [ ] Ollama, if used, is not published to the internet (it has no `ports:` in the compose file)
