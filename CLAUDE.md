# HeroesAndMore - Collectibles Marketplace

## Project Overview
A full-featured collectibles marketplace and community platform built with Django.

## Tech Stack
- **Backend**: Django 6.0, Python 3.12
- **Database**: PostgreSQL (SQLite for local dev)
- **Cache/Queue**: Redis, Celery
- **Frontend**: Bootstrap 5, HTMX
- **Payments**: Stripe Connect
- **Deployment**: Ansible, Nginx, Supervisor, DigitalOcean

## Project Structure
```
herosandmore/
├── app/                    # Django project settings
├── accounts/               # User auth, profiles
├── user_collections/       # Collection management (URL namespace: 'collections')
├── items/                  # Item database & categories
├── marketplace/            # Listings, orders, payments
├── social/                 # Forums, messaging, follows
├── alerts/                 # Wishlists, notifications
├── templates/              # HTML templates
├── static/                 # CSS, JS, images
├── ansible/                # Deployment automation
└── config.py               # Local config (gitignored)
```

**Note:** The `user_collections` app is named this way to avoid conflicts with Python's built-in `collections` module. URL namespace is still 'collections'.

## Local Development

### Setup
```bash
cd /home/john/herosandmore
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Run Celery (for background tasks)
```bash
celery -A app worker -l info
celery -A app beat -l info
```

### Create initial categories
```bash
python manage.py shell
# Then run the seed script or add via admin
```

## Key URLs
- `/` - Homepage
- `/items/` - Browse categories
- `/marketplace/` - All listings
- `/collections/` - Browse collections
- `/social/forums/` - Forums
- `/admin/` - Django admin

## Key Models
- `accounts.Profile` - User profiles, seller verification
- `items.Category` - Hierarchical categories
- `items.Item` - Base item database
- `marketplace.Listing` - For sale items
- `marketplace.Order` - Purchases
- `collections.Collection` - User collections
- `alerts.Wishlist` - Want lists
- `social.Follow` - User follows
- `social.ForumThread` - Forum discussions

## Deployment

### Initial Server Setup
```bash
cd ansible
ansible-playbook -i servers setup.yml
```

### Deploy Updates
```bash
cd ansible
ansible-playbook -i servers gitpull.yml
```

### Check Logs
```bash
ansible -i servers all -m shell -a "tail -100 /var/log/herosandmore/herosandmore.log" --become
```

### Restart Services
```bash
ansible -i servers all -m shell -a "supervisorctl restart herosandmore:*" --become
```

## Config Values Needed (config.py)
- `SECRET_KEY` - Django secret key
- `DATABASE_PASSWORD` - PostgreSQL password
- `STRIPE_PUBLIC_KEY` - Stripe publishable key
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing
- `DO_SPACES_KEY` - DigitalOcean Spaces access key
- `DO_SPACES_SECRET` - DigitalOcean Spaces secret

## Common Tasks

### Add New Category
Go to `/admin/items/category/` and add via Django admin.

### Check Pending Orders
```bash
ansible -i ansible/servers all -m shell -a "cd /home/www/herosandmore && venv/bin/python manage.py shell -c \"from marketplace.models import Order; print(Order.objects.filter(status='pending').count())\"" --become --become-user=www
```

### Database Backup
```bash
ansible -i ansible/servers all -m shell -a "sudo -u postgres pg_dump herosandmore > /tmp/herosandmore_backup.sql" --become
```

## Notes
- The `collections` app uses `item_collections` as the related_name to avoid conflicts with Django's built-in collections module
- All listing images are stored in `media/listings/`
- User avatars are stored in `media/avatars/`
- Platform fee is 3% (configurable in settings.PLATFORM_FEE_PERCENT)
