from peewee import *
import os

# MySQL database configuration with SSL support
db = MySQLDatabase(
    os.getenv('MYSQL_DB', 'github_scrapper'),
    user=os.getenv('MYSQL_USER', 'root'),
    password=os.getenv('MYSQL_PASSWORD', 'password'),
    host=os.getenv('MYSQL_HOST', 'localhost'),
    port=int(os.getenv('MYSQL_PORT', '3306')),
    ssl_ca=os.getenv('MYSQL_SSL_CA'),  # Path to SSL CA certificate file
    ssl_cert=os.getenv('MYSQL_SSL_CERT'),  # Path to SSL client certificate file (optional)
    ssl_key=os.getenv('MYSQL_SSL_KEY'),  # Path to SSL client key file (optional)
    ssl_verify_cert=os.getenv('MYSQL_SSL_VERIFY_CERT', 'true').lower() == 'true',  # Verify SSL certificate
    ssl_verify_identity=os.getenv('MYSQL_SSL_VERIFY_IDENTITY', 'true').lower() == 'true'  # Verify SSL identity
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
    last_attempt_time = DateTimeField(null=True)  # Track when field update was last attempted (for queue prioritization)
    class Meta:
        database = db
        indexes = (
            (('username', 'product_id'), True),  # Unique constraint
            (('is_fields_updated',), False),     # Index for faster filtering by update status
            (('last_attempt_time',), False),     # Index for queue ordering
        )        

def init_db():
    db.connect()
    db.create_tables([Product, ScrapperState, SyncedProduct], safe=True)
    
    # Migrate existing SyncedProduct table to add last_attempt_time field if it doesn't exist
    try:
        # Check if last_attempt_time column exists (MySQL syntax)
        cursor = db.execute_sql("DESCRIBE SyncedProduct")
        columns = [row[0] for row in cursor.fetchall()]
        
        if 'last_attempt_time' not in columns:
            print("🔄 Adding last_attempt_time field to SyncedProduct table...")
            db.execute_sql("ALTER TABLE SyncedProduct ADD COLUMN last_attempt_time DATETIME NULL")
            print("✅ Migration completed successfully")
        else:
            print("ℹ️  last_attempt_time field already exists")
            
    except Exception as e:
        print(f"⚠️  Migration warning: {e}")
        print("ℹ️  This is normal for new databases or if the field already exists")
