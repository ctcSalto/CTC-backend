from external_services.moodle_api.moodle_config import CourseFormat
from typing import Dict, Optional, Union
from dataclasses import dataclass

@dataclass
class Course:
    fullname: str
    shortname: str
    categoryid: int = 1
    summary: str = ""
    format: str = "topics"
    numsections: int = 10
    visible: int = 1
    startdate: Optional[int] = None
    enddate: Optional[int] = None
    
    def to_payload(self, index: int = 0) -> Dict[str, Union[str, int]]:
        payload = {
            f"courses[{index}][fullname]": self.fullname,
            f"courses[{index}][shortname]": self.shortname,
            f"courses[{index}][categoryid]": self.categoryid,
            f"courses[{index}][summary]": self.summary,
            f"courses[{index}][format]": self.format,
            f"courses[{index}][numsections]": self.numsections,
            f"courses[{index}][visible]": self.visible,
        }
        
        if self.startdate:
            payload[f"courses[{index}][startdate]"] = self.startdate
        if self.enddate:
            payload[f"courses[{index}][enddate]"] = self.enddate
            
        return payload