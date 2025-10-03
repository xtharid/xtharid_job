from peewee import *

db = SqliteDatabase("data/scraper.db")

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

def init_db():
    db.connect()
    db.create_tables([Product, ScrapperState], safe=True)
