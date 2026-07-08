# Spice Route – Restaurant Ordering App

A simple Flask-based restaurant ordering application: customers browse the
menu, add items to a cart, and place orders; admins manage the menu and
update order status. Built to be deployed on AWS (EC2 + Docker + RDS +
ALB + Auto Scaling), but works standalone for local testing first.

## Features
- Customer registration & login
- Browse menu, add to cart, place order, view order status
- Admin dashboard: view all orders, update order status
- Admin menu management: add/delete menu items
- `/health` endpoint for load balancer health checks

## Run locally (without Docker)

1. Install MySQL locally (or use any reachable MySQL instance).
2. Create the database and tables:
   ```
   mysql -u root -p < schema.sql
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Set environment variables (adjust to your MySQL setup):
   ```
   export DB_HOST=localhost
   export DB_USER=root
   export DB_PASSWORD=yourpassword
   export DB_NAME=restaurant_db
   export SECRET_KEY=some-random-string
   ```
5. Run the app:
   ```
   python app.py
   ```
6. Visit http://localhost:5000

## Run with Docker

1. Build the image:
   ```
   docker build -t restaurant-app .
   ```
2. Run the container (pointing to a MySQL host reachable from the container):
   ```
   docker run -p 5000:5000 \
     -e DB_HOST=your-db-host \
     -e DB_USER=root \
     -e DB_PASSWORD=yourpassword \
     -e DB_NAME=restaurant_db \
     -e SECRET_KEY=some-random-string \
     restaurant-app
   ```
3. Visit http://localhost:5000

## Creating an admin user

Register a normal account via `/register`, then manually update its role in
the database:
```sql
UPDATE users SET role = 'admin' WHERE username = 'your_username';
```

## Deploying on AWS

This app is designed to run in a Docker container on EC2 instances inside
private subnets, behind an Application Load Balancer, with:
- **RDS MySQL** as the database (set `DB_HOST` to the RDS endpoint)
- **Auto Scaling Group** managing EC2 instance count
- **`/health`** used by the Target Group for health checks
- **GitHub Actions** building and pushing the Docker image, then deploying
- **CloudWatch + SNS** for monitoring and alerts
- **Terraform** provisioning all of the above

See the main project README for the full AWS architecture and deployment steps.
