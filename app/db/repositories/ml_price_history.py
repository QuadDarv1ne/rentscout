"""
CRUD operations for ML price history.
Repository for managing historical price data in the database.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from app.db.models.ml_price_history import MLPriceHistory
from app.utils.logger import logger


class MLPriceHistoryRepository:
    """Repository for ML price history operations."""
    
    @staticmethod
    def add_price(
        db: Session,
        city: str,
        price: float,
        rooms: Optional[int] = None,
        area: Optional[float] = None,
        district: Optional[str] = None,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        source: Optional[str] = None,
        external_id: Optional[str] = None,
        property_type: str = "apartment",
        is_verified: bool = False,
        is_active: bool = True,
    ) -> MLPriceHistory:
        """Add a new price record to history."""
        try:
            history_record = MLPriceHistory(
                city=city,
                price=price,
                rooms=rooms,
                area=area,
                district=district,
                floor=floor,
                total_floors=total_floors,
                source=source,
                external_id=external_id,
                property_type=property_type,
                is_verified=1 if is_verified else 0,
                is_active=1 if is_active else 0,
            )
            db.add(history_record)
            db.commit()
            db.refresh(history_record)
            logger.info(f"Added price history: {city} - {price} RUB")
            return history_record
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add price history: {e}")
            raise
    
    @staticmethod
    def get_by_city(
        db: Session,
        city: str,
        days: int = 30,
        rooms: Optional[int] = None,
        limit: int = 1000,
    ) -> List[MLPriceHistory]:
        """Get price history for a city in the last N days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days + 1)
            
            query = db.query(MLPriceHistory).filter(
                and_(
                    MLPriceHistory.city == city,
                    MLPriceHistory.is_active == 1,
                    or_(
                        MLPriceHistory.recorded_at == None,
                        MLPriceHistory.recorded_at >= cutoff_date,
                    ),
                )
            )
            
            if rooms is not None:
                query = query.filter(MLPriceHistory.rooms == rooms)
            
            records = query.order_by(desc(MLPriceHistory.recorded_at)).limit(limit).all()
            logger.info(f"Retrieved {len(records)} price history records for {city}")
            return records
        except Exception as e:
            logger.error(f"Failed to get price history for {city}: {e}")
            return []
    
    @staticmethod
    def get_by_district(
        db: Session,
        city: str,
        district: str,
        days: int = 30,
        limit: int = 500,
    ) -> List[MLPriceHistory]:
        """Get price history for a specific district."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days + 1)
            
            records = db.query(MLPriceHistory).filter(
                and_(
                    MLPriceHistory.city == city,
                    MLPriceHistory.district == district,
                    MLPriceHistory.is_active == 1,
                    or_(
                        MLPriceHistory.recorded_at == None,
                        MLPriceHistory.recorded_at >= cutoff_date,
                    ),
                )
            ).order_by(desc(MLPriceHistory.recorded_at)).limit(limit).all()
            
            logger.info(f"Retrieved {len(records)} records for {city}/{district}")
            return records
        except Exception as e:
            logger.error(f"Failed to get district history: {e}")
            return []
    
    @staticmethod
    def get_statistics(
        db: Session,
        city: str,
        rooms: Optional[int] = None,
        days: int = 30,
    ) -> dict:
        """Calculate statistics for prices in a city."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days + 1)
            
            query = db.query(MLPriceHistory).filter(
                and_(
                    MLPriceHistory.city == city,
                    MLPriceHistory.is_active == 1,
                    or_(
                        MLPriceHistory.recorded_at == None,
                        MLPriceHistory.recorded_at >= cutoff_date,
                    ),
                )
            )
            
            if rooms is not None:
                query = query.filter(MLPriceHistory.rooms == rooms)
            
            records = query.all()
            
            if not records:
                return {
                    'count': 0,
                    'avg_price': 0,
                    'min_price': 0,
                    'max_price': 0,
                    'median_price': 0,
                }
            
            prices = [r.price for r in records]
            prices.sort()
            
            avg_price = sum(prices) / len(prices)
            median_price = prices[len(prices) // 2]
            
            return {
                'count': len(records),
                'avg_price': round(avg_price, 2),
                'min_price': min(prices),
                'max_price': max(prices),
                'median_price': median_price,
                'std_dev': _calculate_std_dev(prices),
                'total_days': days,
                'city': city,
                'rooms': rooms,
            }
        except Exception as e:
            logger.error(f"Failed to calculate statistics: {e}")
            return {'count': 0}
    
    @staticmethod
    def get_trend(
        db: Session,
        city: str,
        rooms: Optional[int] = None,
        days: int = 30,
    ) -> dict:
        """Analyze price trend over time."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days + 1)
            
            query = db.query(MLPriceHistory).filter(
                and_(
                    MLPriceHistory.city == city,
                    MLPriceHistory.is_active == 1,
                    or_(
                        MLPriceHistory.recorded_at == None,
                        MLPriceHistory.recorded_at >= cutoff_date,
                    ),
                )
            )
            
            if rooms is not None:
                query = query.filter(MLPriceHistory.rooms == rooms)
            
            records = query.order_by(MLPriceHistory.recorded_at).all()
            
            if len(records) < 2:
                return {
                    'trend': 'insufficient_data',
                    'change_percent': 0,
                    'samples': len(records),
                }
            
            # Compare first and second half
            mid_point = len(records) // 2
            first_half = [r.price for r in records[:mid_point]]
            second_half = [r.price for r in records[mid_point:]]
            
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            
            change_percent = ((avg_second - avg_first) / avg_first * 100) if avg_first > 0 else 0
            
            if change_percent > 2:
                trend = 'increasing'
            elif change_percent < -2:
                trend = 'decreasing'
            else:
                trend = 'stable'
            
            return {
                'trend': trend,
                'change_percent': round(change_percent, 2),
                'first_half_avg': round(avg_first, 2),
                'second_half_avg': round(avg_second, 2),
                'samples': len(records),
                'days': days,
            }
        except Exception as e:
            logger.error(f"Failed to analyze trend: {e}")
            return {'trend': 'error'}
    
    @staticmethod
    def delete_old_records(db: Session, days: int = 365) -> int:
        """Delete price history older than specified days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            count = db.query(MLPriceHistory).filter(
                MLPriceHistory.recorded_at < cutoff_date
            ).delete()
            
            db.commit()
            logger.info(f"Deleted {count} old price history records")
            return count
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete old records: {e}")
            raise
    
    @staticmethod
    def get_total_count(db: Session) -> int:
        """Get total count of price history records."""
        try:
            count = db.query(func.count(MLPriceHistory.id)).scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Failed to get total count: {e}")
            return 0
    
    @staticmethod
    def get_city_count(db: Session, city: str) -> int:
        """Get count of price history records for a specific city."""
        try:
            count = db.query(func.count(MLPriceHistory.id)).filter(
                MLPriceHistory.city == city
            ).scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Failed to get city count: {e}")
            return 0


def _calculate_std_dev(values: List[float]) -> float:
    """Calculate standard deviation."""
    if len(values) < 2:
        return 0.0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return round(variance ** 0.5, 2)
