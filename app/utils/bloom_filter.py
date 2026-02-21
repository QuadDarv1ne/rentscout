"""
Bloom Filter для быстрой проверки дубликатов.

Bloom filter - вероятностная структура данных для проверки принадлежности
элемента множеству. Быстрее и экономнее памяти чем set/hashmap для
больших объёмов данных.

Особенности:
- Ложноположительные срабатывания возможны (но редко)
- Ложноотрицательные срабатывания невозможны
- Идеально для дедупликации URL, external_id и т.д.
"""

import math
from typing import Any, Optional, List, Union
from bitarray import bitarray
import hashlib


class BloomFilter:
    """
    Bloom filter для проверки дубликатов.
    
    Пример использования:
        bf = BloomFilter(expected_items=100000, false_positive_rate=0.01)
        
        if not bf.contains(url):
            # Элемент точно новый - обрабатываем
            bf.add(url)
            process_item(item)
        else:
            # Элемент возможно дубликат - пропускаем
            skip_item(item)
    """
    
    def __init__(
        self,
        expected_items: int = 100000,
        false_positive_rate: float = 0.01
    ):
        """
        Инициализация Bloom filter.
        
        Args:
            expected_items: Ожидаемое количество элементов
            false_positive_rate: Допустимая вероятность ложных срабатываний (0.01 = 1%)
        """
        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate
        
        # Вычисляем оптимальные параметры
        self.size = self._calculate_size(expected_items, false_positive_rate)
        self.hash_count = self._calculate_hash_count(self.size, expected_items)
        
        # Инициализируем битовый массив
        self.bit_array = bitarray(self.size)
        self.bit_array.setall(0)
        
        self.elements_added = 0
    
    @staticmethod
    def _calculate_size(n: int, p: float) -> int:
        """
        Вычисляет оптимальный размер битового массива.
        
        Формула: m = -n * ln(p) / (ln(2)^2)
        
        Args:
            n: Количество элементов
            p: Вероятность ложных срабатываний
            
        Returns:
            Размер битового массива в битах
        """
        m = -n * math.log(p) / (math.log(2) ** 2)
        return int(math.ceil(m))
    
    @staticmethod
    def _calculate_hash_count(m: int, n: int) -> int:
        """
        Вычисляет оптимальное количество хеш-функций.
        
        Формула: k = (m/n) * ln(2)
        
        Args:
            m: Размер битового массива
            n: Количество элементов
            
        Returns:
            Количество хеш-функций
        """
        k = (m / n) * math.log(2)
        return int(math.ceil(k))
    
    def _hashes(self, item: Any) -> List[int]:
        """
        Генерирует несколько хешей для элемента.
        
        Использует double hashing для эффективности:
        h(i) = (h1 + i * h2) % size
        
        Args:
            item: Элемент для хеширования
            
        Returns:
            Список индексов битов
        """
        # Преобразуем элемент в байты
        if isinstance(item, bytes):
            item_bytes = item
        else:
            item_bytes = str(item).encode('utf-8')
        
        # Два базовых хеша
        h1 = int(hashlib.md5(item_bytes).hexdigest(), 16)
        h2 = int(hashlib.sha256(item_bytes).hexdigest(), 16)
        
        # Генерируем k хешей
        hashes = []
        for i in range(self.hash_count):
            h = (h1 + i * h2) % self.size
            hashes.append(h)
        
        return hashes
    
    def add(self, item: Any) -> None:
        """
        Добавляет элемент в фильтр.
        
        Args:
            item: Элемент для добавления
        """
        for index in self._hashes(item):
            self.bit_array[index] = 1
        
        self.elements_added += 1
    
    def contains(self, item: Any) -> bool:
        """
        Проверяет наличие элемента в фильтре.
        
        Args:
            item: Элемент для проверки
            
        Returns:
            False - элемент точно отсутствует
            True - элемент возможно присутствует
        """
        for index in self._hashes(item):
            if self.bit_array[index] == 0:
                return False
        
        return True
    
    def __contains__(self, item: Any) -> bool:
        """Поддержка оператора `in`."""
        return self.contains(item)
    
    def __len__(self) -> int:
        """Количество добавленных элементов."""
        return self.elements_added
    
    def clear(self) -> None:
        """Очистить фильтр."""
        self.bit_array.setall(0)
        self.elements_added = 0
    
    @property
    def is_full(self) -> bool:
        """Проверка заполненности фильтра."""
        # Фильтр считается заполненным если более 50% битов установлены
        fill_ratio = self.bit_array.count(1) / self.size
        return fill_ratio > 0.5
    
    def get_stats(self) -> dict:
        """Получить статистику фильтра."""
        fill_ratio = self.bit_array.count(1) / self.size
        
        # Оценка текущей вероятности ложных срабатываний
        # p = (1 - e^(-kn/m))^k
        k = self.hash_count
        n = self.elements_added
        m = self.size
        
        if n == 0:
            estimated_fp_rate = 0
        else:
            estimated_fp_rate = (1 - math.exp(-k * n / m)) ** k
        
        return {
            'size_bits': self.size,
            'hash_count': self.hash_count,
            'elements_added': self.elements_added,
            'fill_ratio': f"{fill_ratio:.2%}",
            'estimated_fp_rate': f"{estimated_fp_rate:.4%}",
            'expected_items': self.expected_items,
            'target_fp_rate': f"{self.false_positive_rate:.2%}",
        }


class DuplicateFilter:
    """
    Комбинированный фильтр дубликатов.
    
    Использует Bloom filter для быстрой проверки + set для точной проверки
    для небольших объёмов данных.
    """
    
    def __init__(
        self,
        expected_items: int = 100000,
        false_positive_rate: float = 0.01,
        use_exact_check: bool = True,
        exact_check_threshold: int = 10000
    ):
        """
        Инициализация фильтра дубликатов.
        
        Args:
            expected_items: Ожидаемое количество элементов
            false_positive_rate: Вероятность ложных срабатываний Bloom filter
            use_exact_check: Использовать ли точную проверку через set
            exact_check_threshold: Порог для переключения на Bloom filter
        """
        self.bloom = BloomFilter(expected_items, false_positive_rate)
        self.exact_set: Optional[set] = set() if use_exact_check else None
        self.exact_check_threshold = exact_check_threshold
        self.use_exact_check = use_exact_check
    
    def is_duplicate(self, key: str) -> bool:
        """
        Проверяет является ли элемент дубликатом.
        
        Args:
            key: Уникальный ключ элемента
            
        Returns:
            True если дубликат, False если новый
        """
        # Если используем точную проверку и set ещё не большой
        if self.use_exact_check and self.exact_set is not None:
            if key in self.exact_set:
                return True
            
            # Добавляем в set
            self.exact_set.add(key)
            
            # Если set стал слишком большим - переключаемся на Bloom filter
            if len(self.exact_set) > self.exact_check_threshold:
                # Переносим все элементы из set в Bloom filter
                for item in self.exact_set:
                    self.bloom.add(item)
                self.exact_set = None  # Освобождаем память
            
            return False
        
        # Используем Bloom filter
        if key in self.bloom:
            return True  # Возможно дубликат
        
        # Точно новый элемент
        self.bloom.add(key)
        return False
    
    def add(self, key: str) -> None:
        """Добавить ключ в фильтр."""
        if self.exact_set is not None:
            self.exact_set.add(key)
        else:
            self.bloom.add(key)
    
    def clear(self) -> None:
        """Очистить фильтр."""
        self.bloom.clear()
        if self.exact_set is None:
            self.exact_set = set()
    
    def get_stats(self) -> dict:
        """Получить статистику фильтра."""
        stats = {
            'mode': 'exact' if self.exact_set is not None else 'bloom',
        }
        
        if self.exact_set is not None:
            stats['exact_set_size'] = len(self.exact_set)
        else:
            stats['bloom_stats'] = self.bloom.get_stats()
        
        return stats


# ============================================================================
# Декоратор для дедупликации
# ============================================================================

def deduplicate(
    key_func: callable,
    filter_instance: Optional[DuplicateFilter] = None
) -> callable:
    """
    Декоратор для автоматической дедупликации результатов функции.
    
    Пример:
        @deduplicate(key_func=lambda x: x['id'])
        async def fetch_items(items):
            return items
    """
    if filter_instance is None:
        filter_instance = DuplicateFilter()
    
    def decorator(func: callable) -> callable:
        async def wrapper(*args, **kwargs) -> list:
            results = await func(*args, **kwargs)
            
            if not results:
                return []
            
            deduplicated = []
            for item in results:
                key = key_func(item)
                if not filter_instance.is_duplicate(key):
                    deduplicated.append(item)
            
            return deduplicated
        
        return wrapper
    
    return decorator


# ============================================================================
# Экспорт
# ============================================================================

__all__ = [
    "BloomFilter",
    "DuplicateFilter",
    "deduplicate",
]
