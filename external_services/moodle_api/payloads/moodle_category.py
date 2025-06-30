from dataclasses import dataclass
from typing import Dict, Union

@dataclass
class Category:
    name: str
    parent: int = 0  # 0 = categoría de nivel superior
    idnumber: str = ""
    description: str = ""
    
    def to_payload(self, index: int = 0) -> Dict[str, Union[str, int]]:
        payload = {
            f"categories[{index}][name]": self.name,
            f"categories[{index}][parent]": self.parent,
            f"categories[{index}][idnumber]": self.idnumber,
            f"categories[{index}][description]": self.description,
        }
        return payload
