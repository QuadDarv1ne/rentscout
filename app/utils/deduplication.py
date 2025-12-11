"""
Duplicate detection and analytics.

Provides comprehensive duplicate detection and analysis with:
- Multiple deduplication strategies
- Fuzzy matching for similar listings
- Duplicate analytics and statistics
- Deduplication recommendations
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from difflib import SequenceMatcher
import hashlib
import json

from app.models.schemas import PropertyCreate
from app.utils.logger import logger
from app.utils.advanced_metrics import metrics_reporter


class DeduplicationStrategy(str, Enum):
    """Deduplication strategies."""
    EXACT = "exact"  # Exact match
    FUZZY = "fuzzy"  # Fuzzy/similar match
    HYBRID = "hybrid"  # Combination of both


@dataclass
class DuplicateMatch:
    """Record of a duplicate match."""
    item1_id: str
    item2_id: str
    source1: str
    source2: str
    similarity_score: float  # 0-1
    matched_fields: List[str] = field(default_factory=list)
    match_reason: str = ""
    detected_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'item1_id': self.item1_id,
            'item2_id': self.item2_id,
            'source1': self.source1,
            'source2': self.source2,
            'similarity_score': round(self.similarity_score, 3),
            'matched_fields': self.matched_fields,
            'match_reason': self.match_reason,
            'detected_at': self.detected_at.isoformat(),
        }


class DuplicateDetector:
    """Detect duplicates in property listings."""
    
    def __init__(
        self,
        fuzzy_threshold: float = 0.85,
        price_tolerance_percent: float = 5.0
    ):
        """
        Initialize duplicate detector.
        
        Args:
            fuzzy_threshold: Similarity threshold for fuzzy matching (0-1)
            price_tolerance_percent: Price difference tolerance (%)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.price_tolerance_percent = price_tolerance_percent
        self.detected_duplicates: List[DuplicateMatch] = []
        self._processed_hashes: Set[str] = set()
    
    def detect_duplicates(
        self,
        items: List[PropertyCreate],
        strategy: DeduplicationStrategy = DeduplicationStrategy.HYBRID
    ) -> Tuple[List[PropertyCreate], List[DuplicateMatch]]:
        """
        Detect and remove duplicates from list.
        
        Args:
            items: List of properties
            strategy: Deduplication strategy
        
        Returns:
            Tuple of (unique items, duplicate matches)
        """
        unique_items = []
        duplicates = []
        seen_hashes: Dict[str, PropertyCreate] = {}
        
        for item in items:
            # Calculate hash
            item_hash = self._calculate_hash(item)
            
            # Exact match detection
            if item_hash in seen_hashes:
                existing = seen_hashes[item_hash]
                match = DuplicateMatch(
                    item1_id=str(existing.id) if hasattr(existing, 'id') else "unknown",
                    item2_id=str(item.id) if hasattr(item, 'id') else "unknown",
                    source1=existing.source,
                    source2=item.source,
                    similarity_score=1.0,
                    matched_fields=['all'],
                    match_reason='Exact match (same hash)'
                )
                duplicates.append(match)
                self.detected_duplicates.append(match)
                continue
            
            # Fuzzy match detection
            is_duplicate = False
            if strategy in (DeduplicationStrategy.FUZZY, DeduplicationStrategy.HYBRID):
                for existing in unique_items:
                    score, matched_fields = self._fuzzy_match(item, existing)
                    if score >= self.fuzzy_threshold:
                        match = DuplicateMatch(
                            item1_id=str(existing.id) if hasattr(existing, 'id') else "unknown",
                            item2_id=str(item.id) if hasattr(item, 'id') else "unknown",
                            source1=existing.source,
                            source2=item.source,
                            similarity_score=score,
                            matched_fields=matched_fields,
                            match_reason=f'Fuzzy match ({score:.1%} similar)'
                        )
                        duplicates.append(match)
                        self.detected_duplicates.append(match)
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_items.append(item)
                seen_hashes[item_hash] = item
        
        # Report metrics
        if duplicates:
            metrics_reporter.record_duplicate_detection(
                source="mixed",
                count=len(duplicates)
            )
        
        logger.info(
            f"Duplicate detection: {len(items)} items → "
            f"{len(unique_items)} unique, "
            f"{len(duplicates)} duplicates removed"
        )
        
        return unique_items, duplicates
    
    def _calculate_hash(self, item: PropertyCreate) -> str:
        """
        Calculate hash for an item.
        
        Args:
            item: Property to hash
        
        Returns:
            Hash string
        """
        # Key fields for hashing
        key_fields = {
            'address': getattr(item, 'address', ''),
            'price': getattr(item, 'price', 0),
            'rooms': getattr(item, 'rooms', 0),
            'area': getattr(item, 'area', 0),
            'source': getattr(item, 'source', ''),
        }
        
        hash_input = json.dumps(key_fields, sort_keys=True, default=str)
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _fuzzy_match(
        self,
        item1: PropertyCreate,
        item2: PropertyCreate
    ) -> Tuple[float, List[str]]:
        """
        Perform fuzzy matching between two items.
        
        Args:
            item1: First property
            item2: Second property
        
        Returns:
            Tuple of (similarity_score, matched_fields)
        """
        matched_fields = []
        scores = []
        
        # Address similarity
        addr1 = getattr(item1, 'address', '').lower()
        addr2 = getattr(item2, 'address', '').lower()
        if addr1 and addr2:
            addr_score = SequenceMatcher(None, addr1, addr2).ratio()
            if addr_score > 0.8:
                matched_fields.append('address')
                scores.append(addr_score * 0.4)  # Weight 40%
        
        # Price similarity
        price1 = getattr(item1, 'price', None)
        price2 = getattr(item2, 'price', None)
        if price1 and price2 and price1 > 0:
            price_diff = abs(price1 - price2) / price1 * 100
            if price_diff <= self.price_tolerance_percent:
                matched_fields.append('price')
                scores.append((1 - price_diff / 100) * 0.3)  # Weight 30%
        
        # Rooms similarity
        rooms1 = getattr(item1, 'rooms', None)
        rooms2 = getattr(item2, 'rooms', None)
        if rooms1 and rooms2:
            if rooms1 == rooms2:
                matched_fields.append('rooms')
                scores.append(1.0 * 0.2)  # Weight 20%
        
        # Area similarity
        area1 = getattr(item1, 'area', None)
        area2 = getattr(item2, 'area', None)
        if area1 and area2 and area1 > 0:
            area_diff = abs(area1 - area2) / area1 * 100
            if area_diff <= 10:  # 10% tolerance
                matched_fields.append('area')
                scores.append((1 - area_diff / 100) * 0.1)  # Weight 10%
        
        overall_score = sum(scores) if scores else 0
        return overall_score, matched_fields
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get duplicate detection statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self.detected_duplicates:
            return {
                'total_duplicates': 0,
                'duplicates_by_source_pair': {},
                'average_similarity': 0,
            }
        
        # Count by source pair
        source_pairs: Dict[str, int] = {}
        for match in self.detected_duplicates:
            key = f"{match.source1}↔{match.source2}"
            source_pairs[key] = source_pairs.get(key, 0) + 1
        
        # Average similarity
        avg_similarity = sum(
            m.similarity_score for m in self.detected_duplicates
        ) / len(self.detected_duplicates) if self.detected_duplicates else 0
        
        return {
            'total_duplicates': len(self.detected_duplicates),
            'duplicates_by_source_pair': source_pairs,
            'average_similarity': round(avg_similarity, 3),
            'exact_matches': sum(
                1 for m in self.detected_duplicates if m.similarity_score == 1.0
            ),
            'fuzzy_matches': sum(
                1 for m in self.detected_duplicates if m.similarity_score < 1.0
            ),
        }
    
    def clear_history(self):
        """Clear duplicate detection history."""
        self.detected_duplicates.clear()
        self._processed_hashes.clear()
        logger.info("Duplicate detection history cleared")


class DeduplicationAnalyzer:
    """Analyze deduplication effectiveness."""
    
    @staticmethod
    def analyze_deduplication_impact(
        original_count: int,
        unique_count: int
    ) -> Dict[str, Any]:
        """
        Analyze deduplication impact.
        
        Args:
            original_count: Count before deduplication
            unique_count: Count after deduplication
        
        Returns:
            Impact analysis
        """
        duplicates_removed = original_count - unique_count
        dedup_rate = (duplicates_removed / original_count * 100) if original_count > 0 else 0
        
        return {
            'original_count': original_count,
            'unique_count': unique_count,
            'duplicates_removed': duplicates_removed,
            'deduplication_rate_percent': round(dedup_rate, 2),
            'efficiency': 'High' if dedup_rate > 10 else 'Medium' if dedup_rate > 5 else 'Low',
        }
    
    @staticmethod
    def get_deduplication_recommendations(
        stats: Dict[str, Any],
        duplicates: List[DuplicateMatch]
    ) -> List[Dict[str, str]]:
        """
        Get recommendations based on deduplication analysis.
        
        Args:
            stats: Deduplication statistics
            duplicates: List of duplicate matches
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if stats['deduplication_rate_percent'] > 20:
            recommendations.append({
                'issue': 'High duplication rate (>20%)',
                'suggestion': 'Review data quality and source coordination',
                'priority': 'high'
            })
        
        if stats['exact_matches'] > len(duplicates) * 0.5:
            recommendations.append({
                'issue': 'Many exact duplicates',
                'suggestion': 'Consider data synchronization between sources',
                'priority': 'medium'
            })
        
        if stats['average_similarity'] > 0.95 and stats['fuzzy_matches'] > 0:
            recommendations.append({
                'issue': 'Many fuzzy matches with high similarity',
                'suggestion': 'Standardize address formats and data normalization',
                'priority': 'medium'
            })
        
        if stats['deduplication_rate_percent'] < 1:
            recommendations.append({
                'issue': 'Low deduplication rate',
                'suggestion': 'Sources appear to be well-coordinated. Good!',
                'priority': 'low'
            })
        
        return recommendations


# Global instances
duplicate_detector = DuplicateDetector()
dedup_analyzer = DeduplicationAnalyzer()
