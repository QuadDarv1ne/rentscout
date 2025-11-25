import logging
from typing import List
from app.models.schemas import PropertyCreate
from app.db.elastic import es

logger = logging.getLogger(__name__)

async def save_properties(properties: List[PropertyCreate]):
    """Save properties to Elasticsearch."""
    try:
        for property in properties:
            # Convert Pydantic model to dict
            property_dict = property.model_dump()
            
            # Index the property in Elasticsearch
            await es.index(
                index="properties",
                body=property_dict,
                id=property_dict["external_id"]
            )
        
        logger.info(f"Successfully saved {len(properties)} properties to Elasticsearch")
        
    except Exception as e:
        logger.error(f"Error saving properties to Elasticsearch: {e}")
        raise