from peewee import *
import os

# Get the project root directory (where db.py is located)
project_root = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(project_root, "data")

# Create data directory if it doesn't exist
os.makedirs(data_dir, exist_ok=True)

db = SqliteDatabase(os.path.join(data_dir, "scraper.db"))

class Product(Model):
    id = IntegerField()
    product_id = CharField(primary_key=True)
    json_data = TextField()
    class Meta:
        database = db

class ScrapperState(Model):
    offset = IntegerField(default=0)
    class Meta:
        database = db

class SyncedProduct(Model):
    username = CharField()
    product_id = CharField()
    proc_id = IntegerField()  # API procedure ID (required)
    is_fields_updated = BooleanField(default=False)  # Track if product fields were updated
    synced_at = DateTimeField()
    class Meta:
        database = db
        indexes = (
            (('username', 'product_id'), True),  # Unique constraint
            (('is_fields_updated',), False),     # Index for faster filtering by update status
        )        

def init_db():
    db.connect()
    db.create_tables([Product, ScrapperState, SyncedProduct], safe=True)
