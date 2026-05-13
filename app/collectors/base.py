import logging
from abc import ABC, abstractmethod
from typing import List, Dict


class BaseCollector(ABC):
    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def collect(self) -> List[Dict]:
        """Run collection and return a list of raw data dicts."""
