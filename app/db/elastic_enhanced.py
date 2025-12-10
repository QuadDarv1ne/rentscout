"""Enhanced Elasticsearch integration for advanced search and analytics."""

from typing import List, Dict, Any, Optional, Tuple
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ElasticsearchException
from app.utils.logger import logger
from app.core.config import settings


class ElasticsearchClient:
    """Enhanced Elasticsearch client for advanced operations."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        index_name: str = "properties",
    ):
        """Initialize Elasticsearch client.
        
        Args:
            host: Elasticsearch host
            port: Elasticsearch port
            index_name: Index name for properties
        """
        try:
            self.client = Elasticsearch([{"host": host, "port": port}])
            self.index_name = index_name
            self.client.info()  # Test connection
            logger.info(f"✅ Connected to Elasticsearch at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check if connected to Elasticsearch.
        
        Returns:
            True if connected
        """
        if not self.client:
            return False
        
        try:
            self.client.info()
            return True
        except Exception as e:
            logger.warning(f"Elasticsearch connection check failed: {e}")
            return False
    
    async def index_property(
        self,
        property_id: str,
        data: Dict[str, Any],
    ) -> bool:
        """Index a property in Elasticsearch.
        
        Args:
            property_id: Unique property ID
            data: Property data to index
            
        Returns:
            True if successful
        """
        if not self.client:
            logger.warning("Elasticsearch client not available")
            return False
        
        try:
            self.client.index(
                index=self.index_name,
                id=property_id,
                document=data,
            )
            logger.debug(f"Property {property_id} indexed in Elasticsearch")
            return True
        except ElasticsearchException as e:
            logger.error(f"Failed to index property {property_id}: {e}")
            return False
    
    async def bulk_index_properties(
        self,
        properties: List[Tuple[str, Dict[str, Any]]],
    ) -> Tuple[int, int]:
        """Bulk index multiple properties.
        
        Args:
            properties: List of (property_id, data) tuples
            
        Returns:
            Tuple of (successful, failed) counts
        """
        if not self.client:
            logger.warning("Elasticsearch client not available")
            return 0, len(properties)
        
        successful = 0
        failed = 0
        
        try:
            from elasticsearch.helpers import bulk
            
            actions = []
            for property_id, data in properties:
                actions.append({
                    "_index": self.index_name,
                    "_id": property_id,
                    "_source": data,
                })
            
            results = bulk(self.client, actions)
            successful = results[0]
            failed = len(properties) - successful
            
            logger.info(f"Bulk indexed {successful} properties, {failed} failed")
            return successful, failed
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            return 0, len(properties)
    
    async def search_properties(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        from_: int = 0,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Advanced property search using Elasticsearch.
        
        Args:
            query: Search query string
            filters: Optional filtering parameters
            from_: Pagination offset
            size: Number of results
            
        Returns:
            Search results
        """
        if not self.client:
            logger.warning("Elasticsearch client not available")
            return {"hits": {"hits": [], "total": {"value": 0}}}
        
        try:
            search_query: Dict[str, Any] = {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["title^2", "description", "address"],
                            }
                        }
                    ],
                    "filter": [],
                }
            }
            
            # Add filters
            if filters:
                if "min_price" in filters:
                    search_query["bool"]["filter"].append(
                        {"range": {"price": {"gte": filters["min_price"]}}}
                    )
                if "max_price" in filters:
                    search_query["bool"]["filter"].append(
                        {"range": {"price": {"lte": filters["max_price"]}}}
                    )
                if "city" in filters:
                    search_query["bool"]["filter"].append(
                        {"term": {"city.keyword": filters["city"]}}
                    )
                if "property_type" in filters:
                    search_query["bool"]["filter"].append(
                        {"term": {"property_type.keyword": filters["property_type"]}}
                    )
                if "min_rooms" in filters:
                    search_query["bool"]["filter"].append(
                        {"range": {"rooms": {"gte": filters["min_rooms"]}}}
                    )
                if "max_rooms" in filters:
                    search_query["bool"]["filter"].append(
                        {"range": {"rooms": {"lte": filters["max_rooms"]}}}
                    )
                if "min_area" in filters:
                    search_query["bool"]["filter"].append(
                        {"range": {"area": {"gte": filters["min_area"]}}}
                    )
                if "max_area" in filters:
                    search_query["bool"]["filter"].append(
                        {"range": {"area": {"lte": filters["max_area"]}}}
                    )
            
            results = self.client.search(
                index=self.index_name,
                query=search_query,
                from_=from_,
                size=size,
            )
            
            total_hits = results["hits"]["total"]["value"]
            logger.debug(f"Found {total_hits} properties")
            return results
        except ElasticsearchException as e:
            logger.error(f"Search failed: {e}")
            return {"hits": {"hits": [], "total": {"value": 0}}}
    
    async def get_aggregations(
        self,
        field: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 20,
    ) -> Dict[str, Any]:
        """Get aggregations for analytics.
        
        Args:
            field: Field to aggregate on
            filters: Optional filtering parameters
            size: Maximum number of buckets
            
        Returns:
            Aggregation results
        """
        if not self.client:
            logger.warning("Elasticsearch client not available")
            return {}
        
        try:
            agg_query: Dict[str, Any] = {
                "agg_field": {
                    "terms": {
                        "field": f"{field}.keyword",
                        "size": size,
                    }
                }
            }
            
            filter_clause: Dict[str, Any] = {"bool": {"filter": []}}
            
            if filters and "city" in filters:
                filter_clause["bool"]["filter"].append(
                    {"term": {"city.keyword": filters["city"]}}
                )
            
            search_body = {
                "aggs": agg_query,
            }
            
            if filter_clause["bool"]["filter"]:
                search_body["query"] = filter_clause
            
            results = self.client.search(
                index=self.index_name,
                aggs=agg_query,
            )
            
            return results.get("aggregations", {})
        except ElasticsearchException as e:
            logger.error(f"Aggregation failed: {e}")
            return {}
    
    async def get_price_stats(
        self,
        city: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get price statistics for properties.
        
        Args:
            city: Optional city filter
            
        Returns:
            Price statistics (min, max, avg, percentiles)
        """
        if not self.client:
            logger.warning("Elasticsearch client not available")
            return {}
        
        try:
            agg_query: Dict[str, Any] = {
                "price_stats": {
                    "stats": {"field": "price"}
                },
                "price_percentiles": {
                    "percentiles": {
                        "field": "price",
                        "percents": [25, 50, 75, 90],
                    }
                },
            }
            
            filter_clause = {}
            if city:
                filter_clause = {
                    "query": {"term": {"city.keyword": city}}
                }
            
            results = self.client.search(
                index=self.index_name,
                aggs=agg_query,
                **filter_clause,
                size=0,
            )
            
            return results.get("aggregations", {})
        except ElasticsearchException as e:
            logger.error(f"Price stats failed: {e}")
            return {}
    
    async def delete_property(self, property_id: str) -> bool:
        """Delete a property from Elasticsearch.
        
        Args:
            property_id: Property ID to delete
            
        Returns:
            True if successful
        """
        if not self.client:
            logger.warning("Elasticsearch client not available")
            return False
        
        try:
            self.client.delete(
                index=self.index_name,
                id=property_id,
            )
            logger.debug(f"Property {property_id} deleted from Elasticsearch")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete property {property_id}: {e}")
            return False
    
    async def create_index(self, mappings: Optional[Dict[str, Any]] = None) -> bool:
        """Create index with optional custom mappings.
        
        Args:
            mappings: Optional Elasticsearch mappings
            
        Returns:
            True if successful
        """
        if not self.client:
            logger.warning("Elasticsearch client not available")
            return False
        
        try:
            if self.client.indices.exists(index=self.index_name):
                logger.debug(f"Index {self.index_name} already exists")
                return True
            
            default_mappings = {
                "properties": {
                    "title": {"type": "text", "analyzer": "standard"},
                    "description": {"type": "text", "analyzer": "standard"},
                    "price": {"type": "integer"},
                    "area": {"type": "float"},
                    "rooms": {"type": "integer"},
                    "city": {"type": "keyword"},
                    "address": {"type": "text"},
                    "property_type": {"type": "keyword"},
                    "source": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                }
            }
            
            final_mappings = mappings or default_mappings
            
            self.client.indices.create(
                index=self.index_name,
                mappings=final_mappings,
            )
            logger.info(f"Index {self.index_name} created successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False
    
    async def get_health(self) -> Dict[str, Any]:
        """Get Elasticsearch cluster health.
        
        Returns:
            Health status
        """
        if not self.client:
            return {"status": "disconnected"}
        
        try:
            health = self.client.cluster.health()
            return {
                "status": health.get("status"),
                "active_shards": health.get("active_shards"),
                "indices": health.get("number_of_indices"),
            }
        except Exception as e:
            logger.warning(f"Failed to get cluster health: {e}")
            return {"status": "error", "error": str(e)}


# Global instance
es_client: Optional[ElasticsearchClient] = None


def get_es_client() -> Optional[ElasticsearchClient]:
    """Get global Elasticsearch client instance.
    
    Returns:
        ElasticsearchClient or None if not initialized
    """
    global es_client
    if es_client is None:
        try:
            es_client = ElasticsearchClient(
                host=settings.ELASTICSEARCH_HOST,
                port=settings.ELASTICSEARCH_PORT,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize Elasticsearch: {e}")
    
    return es_client
