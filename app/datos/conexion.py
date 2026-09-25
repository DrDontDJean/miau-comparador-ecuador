from functools import lru_cache
from pymongo import MongoClient


@lru_cache(maxsize=4)
def cliente(uri):
    return MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                       socketTimeoutMS=30000, tz_aware=True, appname='FrecuentoEtapa1')


def conectar(config):
    return cliente(config.mongo_uri)[config.mongo_db]
