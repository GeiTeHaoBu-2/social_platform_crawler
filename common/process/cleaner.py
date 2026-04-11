from typing import List
from common.models.item import HotSearchItem


class Cleaner:
    def clean(self, raw_data: List[HotSearchItem]) -> List[HotSearchItem]:
        for item in raw_data:
            if item.title:
                item.title = item.title.strip()
            if item.url:
                item.url = item.url.strip()
        return raw_data
