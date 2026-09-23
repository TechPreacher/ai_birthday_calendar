# AI Birthday Calendar / Tracker

A self-hosted birthday tracker with AI-powered gift suggestions and personalized messages. Built with FastAPI, vanilla JavaScript, and OpenAI GPT-4o. Features automated email reminders, user management, and a responsive calendar UI.

![Main birthday tracker screen](./images/tracker1.png)

![Edit a birthday](./images/tracker2.png)

![Settings](./images/tracker3.png)

![User management](./images/tracker4.png)

## Features

- **Yearly Calendar View** - See all birthdays organized by month
- **CRUD Operations** - Create, read, update, and delete birthdays
- **Email Reminders** - Automated daily reminders sent 1 day before birthdays
- **AI-Powered Suggestions** - Optional OpenAI-generated congratulations messages and gift ideas
- **User Authentication** - Secure login with JWT tokens
- **Responsive Design** - Works on mobile and desktop browsers
- **Configurable Settings** - SMTP settings and reminder time configuration via web UI
- **Contact Categorization** - Organize contacts as Friend or Business
- **Self-Hosted & Privacy-Focused** - Your data stays on your server, no database required

## Tech Stack

- **Backend:** FastAPI (Python 3.10+)
- **Frontend:** Vanilla JavaScript, HTML5, CSS3
- **Storage:** JSON files, written atomically (no database required)
- **Authentication:** JWT tokens with bcrypt password hashing
- **Scheduling:** APScheduler for automated email reminders
- **Email:** SMTP (Gmail compatible)
- **AI:** OpenAI GPT-4o (optional)
- **Deployment:** Docker Compose, or systemd on the host

## Installation

### Quick Start (uv)

```bash
# Clone the repository
git clone https://github.com/TechPreacher/ai-birthday-calendar.git
cd ai-birthday-calendar

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your settings (see Configuration below)

# Run the application
uv run uvicorn app.main:app --host 0.0.0.0 --port 8081
```

<details>
<summary>Alternative: pip</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
uvicorn app.main:app --host 0.0.0.0 --port 8081
```

</details>

The app will be available at **<http://localhost:8081>**.

### Docker Compose (recommended for servers)

A `Dockerfile` and `compose.yml` are included. This is the easiest way to run the
app on a server: dependencies are installed from `uv.lock` inside a pinned
Python 3.12 image, so the host's Python version is irrelevant, and no root access
is needed beyond membership of the `docker` group.

```bash
cp .env.example .env
# Set BIRTHDAYS_SECRET_KEY to a long random string and choose admin credentials.
# Leave BIRTHDAYS_DATA_DIR out -- compose.yml sets it to the container path.

docker compose up -d --build
```

The container publishes to **127.0.0.1:8081** only, on the assumption that a
reverse proxy terminates TLS in front of it (see below). Data lives in `./data`
on the host via a bind mount, so it stays visible for backups.

Two things to adjust for your environment:

- **`TZ` in `compose.yml`** (default `Europe/Zurich`). APScheduler interprets the
  daily reminder time in the container's local timezone; without this the
  container runs in UTC and reminders fire at the wrong hour.
- **The container runs as uid 1000**, so the bind-mounted `./data` is writable by
  it and readable by a typical first user account. If your account has a
  different uid, change it in the `Dockerfile` or add a `user:` line to
  `compose.yml`.

Everyday commands:

```bash
docker compose ps
docker compose logs -f
docker compose restart
docker compose up -d --build     # after changing app code or dependencies
```

`restart: unless-stopped` starts the app again after a reboot, so no systemd unit
is needed.

<details>
<summary>Reverse proxy example (nginx + Let's Encrypt)</summary>

A template is included at `deploy/nginx-birthdays.corti.com.conf` — rename it for
your own domain. It proxies `https://your.domain` to `127.0.0.1:8081`.

```bash
sudo cp deploy/nginx-<your-domain>.conf /etc/nginx/sites-available/<your-domain>
sudo ln -s /etc/nginx/sites-available/<your-domain> /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <your-domain> --redirect
```

The DNS record must already point at the host before running certbot, or the
HTTP-01 challenge will fail. Note that `nginx -t` needs `sudo`, because
validation opens the TLS private keys.

</details>

### Running as a Systemd Service (Linux)

An alternative to Docker, if you would rather run the app directly on the host.
Note that this ties the app to the host's Python version.

Before installing, edit `birthdays.service` and replace `YOUR_USER` with the user account that should run the service. Also update the paths if you installed to a directory other than `/opt/birthdays`.

```bash
sudo cp birthdays.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable birthdays
sudo systemctl start birthdays

# Check status
sudo systemctl status birthdays
```

## Default Credentials

- **Username:** `admin`
- **Password:** `changeme`

**IMPORTANT:** Change the admin password immediately after first login!

## Configuration

### Environment Variables

Create a `.env` file (or copy from `.env.example`):

```bash
BIRTHDAYS_DATA_DIR=./data
BIRTHDAYS_SECRET_KEY=change-this-to-a-random-secret-key
BIRTHDAYS_ADMIN_USERNAME=admin
BIRTHDAYS_ADMIN_PASSWORD=changeme
```

After changing credentials, restart the application.

**Under Docker, omit `BIRTHDAYS_DATA_DIR`.** `compose.yml` sets it to the
container path (`/data`), which is where `./data` is bind-mounted. A host path
left in `.env` would be meaningless inside the container. Compose's
`environment:` takes precedence over `env_file:`, so a stale value would be
ignored rather than break anything — but leaving it out avoids the confusion.

`BIRTHDAYS_ADMIN_USERNAME` and `BIRTHDAYS_ADMIN_PASSWORD` only **seed** the admin
account, and only when no `admin` user exists in `users.json` yet. Once the
account is created, changing these values in `.env` has no effect — change the
password through the web UI instead.

### Email Notifications

Configure email settings through the web UI:

1. Log in as admin
2. Click **Settings** (gear icon)
3. Enable email notifications
4. Enter SMTP server details:
   - **SMTP Server** - e.g., `smtp.gmail.com`
   - **SMTP Port** - Usually `587` (TLS) or `465` (SSL)
   - **Username** - Your email address
   - **Password** - Your email password or app-specific password
   - **From Email** - The sender address
   - **Recipients** - One email per line
   - **Reminder Time** - Time to send daily reminders (default: 09:00)

**Gmail Users:** You'll need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

**Test Mode:** Enable this to log emails without actually sending them (useful for testing).

### AI Features (Optional)

The app can enhance birthday reminder emails with AI-generated personalized congratulations messages and gift suggestions using OpenAI's GPT-4o model.

#### How It Works

When AI features are enabled, each birthday reminder email includes:

- A warm, personalized congratulations message tailored to the person
- 5 gift suggestions based on their name, age, and any notes you've added

**Example email:**

```
Subject: Birthday Reminder - 2 birthday(s) tomorrow

Birthday Reminder for April 10, 2026

The following people have birthdays tomorrow:

- Jane Doe (turning 30)

  Happy birthday to Jane! Turning 30 is a wonderful milestone...

  Gift Ideas:
  - A premium bottle of wine or craft beer selection
  - A high-quality leather wallet or watch
  - Tickets to a concert or sporting event
  - A personalized photo book or custom artwork
  - An experience gift like a cooking class or spa day
```

#### Setup

1. Get an API key from [OpenAI](https://platform.openai.com/api-keys)
2. In the app, go to **Settings > Email Notifications**
3. Scroll to **AI Features**
4. Check **"Enable AI-generated gift ideas and messages"**
5. Paste your OpenAI API key
6. Click **Save Settings**

**Cost:** Approximately $0.02-$0.04 per birthday using GPT-4o. For 50 birthdays per year, that's roughly $1-2/year.

#### Privacy

- Only birthday information (name, age, notes) is sent to OpenAI
- No email addresses or other personal data is shared
- If the AI call fails, the email is still sent without AI content

To disable AI features at any time, uncheck the option in Settings.

## Usage

### Adding a Birthday

1. Click the **+ Add Birthday** button (bottom right)
2. Enter the name, birth date, and optional birth year
3. Add an optional note (e.g., "Best friend", "Loves gardening")
4. Click **Save**

### Editing a Birthday

1. Click on any birthday in the calendar
2. Modify the details
3. Click **Save** or **Delete**

### Viewing Different Years

Use the year selector in the top navigation to see ages people will turn in different years.

## How Email Reminders Work

- The scheduler checks daily at the configured time (default: 09:00)
- It finds all birthdays happening **tomorrow**
- Sends a single email to all configured recipients
- Includes names, ages (if birth year is known), and notes
- Optionally includes AI-generated messages and gift ideas

## Data Storage

All data is stored as JSON files in your configured data directory:

- `birthdays.json` - Birthday entries
- `users.json` - User accounts and password hashes
- `settings.json` - Email and AI settings

Writes are atomic: each file is written to a temporary file in the same
directory, flushed to disk, then moved into place with `os.replace()`. A reader
therefore sees either the complete old file or the complete new one, and a crash
mid-write cannot truncate the file and lose every record. Each write also
re-applies mode `600`, because the atomic replace creates a new inode that would
otherwise take its permissions from the process umask.

**Backup recommendation:** Regularly back up your data directory. Because writes
are atomic, a plain `tar` of the data directory is safe while the app is running
— there is no need to stop it first.

```bash
tar czf birthdays-data-$(date +%F).tar.gz -C /path/to/app data
chmod 600 birthdays-data-*.tar.gz   # the archive contains the same secrets
```

## API Documentation

Interactive API documentation (Swagger UI at `/docs`, ReDoc at `/redoc`, and the
schema at `/openapi.json`) is **disabled by default**. The endpoints it describes
all require a token, but on a public deployment it advertises the whole API
surface to anyone who asks, and the people using the app never need it.

Enable it when working against the API:

```bash
BIRTHDAYS_ENABLE_DOCS=true
```

Under Docker, add it to the `environment:` block in `compose.yml` and re-create
the container.

## Project Structure

```
ai-birthday-calendar/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app entry point
│   ├── auth.py           # Authentication logic
│   ├── models.py         # Data models (Pydantic)
│   ├── storage.py        # JSON storage layer
│   ├── scheduler.py      # Email reminder scheduler
│   ├── config.py         # Configuration
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py       # Auth endpoints
│   │   ├── birthdays.py  # Birthday CRUD endpoints
│   │   └── settings.py   # Settings endpoints
│   └── static/
│       ├── index.html    # Main UI
│       ├── css/
│       │   └── styles.css
│       └── js/
│           └── app.js    # Frontend logic
├── data/                 # JSON data files (created at runtime)
├── deploy/               # Reverse proxy config template
├── tests/                # Test suite
├── pyproject.toml        # Python dependencies
├── uv.lock               # Dependency lock file
├── Dockerfile            # Container image (Python 3.12, deps from uv.lock)
├── compose.yml           # Docker Compose service definition
├── .dockerignore
├── birthdays.service     # Systemd service file (alternative to Docker)
├── install.sh            # Installation helper script
└── .env.example          # Environment variable template
```

## Troubleshooting

### Check Service Status

```bash
docker compose ps                    # Docker
sudo systemctl status birthdays      # systemd
```

### View Logs

```bash
docker compose logs -f               # Docker
sudo journalctl -u birthdays -f      # systemd
```

### Restart the Service

```bash
docker compose restart               # Docker
sudo systemctl restart birthdays     # systemd
```

### Changes to the Code Not Taking Effect

Under Docker the application code is baked into the image, so a plain restart
will not pick up edits. Rebuild instead:

```bash
docker compose up -d --build
```

### Email Not Sending

1. Check your SMTP credentials in Settings
2. Enable **Test Mode** and check logs for error messages
3. For Gmail, ensure you're using an App Password
4. Check that firewall rules allow outbound SMTP connections

### AI Suggestions Not Appearing

1. Verify AI is enabled in Settings
2. Check that the OpenAI API key is entered correctly (starts with `sk-...`)
3. Ensure your OpenAI account has available credits
4. Check logs for API errors

## Security Notes

- Change the default admin password immediately after setup
- Set `BIRTHDAYS_SECRET_KEY` to a long random string. Anyone who can read it can
  forge a login token, so keep `.env` at mode `600`
- Passwords are hashed with bcrypt
- Consider running behind a reverse proxy (Nginx/Caddy) with HTTPS for production use
- The SMTP password and OpenAI API key are stored in `data/settings.json`. The
  app writes its data files as `600`, but set the directory itself to `700` if
  the machine has other user accounts:

  ```bash
  chmod 700 data
  chmod 600 .env data/*.json
  ```

- `/docs`, `/redoc` and `/openapi.json` are disabled unless
  `BIRTHDAYS_ENABLE_DOCS` is set, so the API surface is not advertised publicly
- Reminder emails escape names, notes and AI-generated text before placing them
  in the HTML body, so a note containing `<` renders as written rather than
  reshaping the message
- The nginx template in `deploy/` rate-limits `/api/auth/token` to slow down
  password guessing. If you front the app some other way, add an equivalent —
  bcrypt makes each attempt expensive, but nothing otherwise caps how many can
  be made

## License

MIT License
