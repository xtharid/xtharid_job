from peewee import *
import os

# MySQL database configuration
db = MySQLDatabase(
    os.getenv('MYSQL_DB', 'github_scrapper'),
    user=os.getenv('MYSQL_USER', 'root'),
    password=os.getenv('MYSQL_PASSWORD', 'password'),
    host=os.getenv('MYSQL_HOST', 'localhost'),
    port=int(os.getenv('MYSQL_PORT', '3306'))
)

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
