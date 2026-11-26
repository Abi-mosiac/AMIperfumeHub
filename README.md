# AMIPerfumeHub

AMIPerfumeHub is a multi-vendor perfume marketplace for customers and approved vendors. The backend uses FastAPI, SQLAlchemy and PostgreSQL. The responsive storefront is built with HTML, CSS and JavaScript and is served by FastAPI.

## Local setup

1. Create and activate a Python virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure `.env` in the project root:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/amiperfumehub
   SECRET_KEY=replace-with-a-long-random-secret
   JWT_ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   ALLOWED_ORIGINS=
   ```

   Keep `.env` private. Leave `ALLOWED_ORIGINS` blank when the browser app is served from this FastAPI process. For a separately hosted frontend, set it to a comma-separated list of exact trusted origins.

3. Apply the numbered PostgreSQL migrations in order and create the first administrator:

   ```bash
   python -m app.migrate
   python -m scripts.create_admin --email admin@example.com --full-name "Marketplace Admin"
   ```

   The admin command prompts for and confirms the password. If the email already belongs to an active user, the command promotes that account and replaces its password.

4. Start the application:

   ```bash
   uvicorn app.main:app --reload
   ```

   Open `http://127.0.0.1:8000`. API documentation is available at `/docs`.

   To open the app on a phone connected to the same Wi-Fi, start Uvicorn on
   your computer's network interface and use that computer's local IP address:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   Then visit `http://<computer-local-IP>:8000` on the phone (for example,
   `http://192.168.1.20:8000`). Allow inbound port 8000 on the computer's
   firewall if needed. For installing the app from a public address, deploy
   behind HTTPS; browsers require a secure connection for service workers and
   app installation. On supported browsers, use **Install app** or **Add to
   Home Screen** from the browser menu.

## Run with Docker Compose

Copy `.env.example` to `.env`, replace both passwords/secrets, then start the app and PostgreSQL:

```bash
docker compose up --build -d
docker compose exec app python -m scripts.create_admin --email admin@example.com --full-name "Marketplace Admin"
```

Compose applies database migrations before starting the API. Use URL-safe characters in `POSTGRES_PASSWORD` because it is included in the SQLAlchemy connection URL. Put a TLS-terminating reverse proxy in front of the app for public hosting.

## Main API flows

- Customer accounts: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`.
- Vendor applications: authenticated `POST /auth/vendor-register`; admins review applications under `/admin/vendors/applications`.
- Vendor profile: approved vendors can view and update `/vendor/profile`.
- Product catalogue: public `GET /products` and `GET /products/{id}`; approved vendors manage their own listings through `/products` and `/products/mine`.
- Cart: customer-only `GET /cart`, `POST /cart/items`, `PUT /cart/items/{id}`, and `DELETE /cart/items/{id}`.
- Checkout and order history: customer-only `POST /orders` and `GET /orders`.
- Vendor fulfilment: `GET /orders/vendor` and vendor-owned order item status updates.
- Dashboards: `/vendor/dashboard` and `/admin/dashboard`; admin management endpoints are under `/admin`.
- Product image upload: approved vendors send multipart `file` data to `POST /products/images`; upload responses provide an image URL for product listings.

Authentication uses bearer JWTs. The frontend stores the token in browser local storage and removes it when the user logs out. Payment on delivery is the only payment method in this release.

## Migrations

Migration files are applied in lexical order and recorded in `schema_migrations`. The runner applies pending migrations in one database transaction. It expects the database to be PostgreSQL and the configured account to have table and index creation privileges.

## Current release boundaries

- Product images can be uploaded as PNG, JPEG, GIF, or WebP files up to 5 MB. Compose stores them in a persistent local volume; a distributed production deployment should use managed object storage.
- Authentication rate limits are held in process memory. A multi-worker or multi-instance deployment should use a shared limiter.
- Configure HTTPS and production secrets at the hosting layer before public deployment.
- No hosting provider or production database credentials are configured in this workspace.
