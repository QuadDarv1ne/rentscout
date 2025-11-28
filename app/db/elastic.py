from elasticsearch import AsyncElasticsearch

from app.core.config import settings

es = AsyncElasticsearch(settings.ELASTICSEARCH_URL)


async def index_property(property: dict):
    await es.index(index="properties", body=property, id=property["external_id"])
