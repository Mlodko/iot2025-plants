from typing import Self
from uuid import UUID
import uuid
import os
import json

from pydantic.main import BaseModel
import pydantic

DEFAULT_POT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pot_config/config.json")

class PotConfig(BaseModel):
    pot_id: UUID = pydantic.Field(default_factory=uuid.uuid4, )
    
    def get_pot_id(self) -> UUID:
        return self.pot_id
    
    def set_pot_id(self, pot_id: UUID) -> None:
        self.pot_id = pot_id
    
    @staticmethod    
    def load_from_file(path: str = DEFAULT_POT_CONFIG_PATH) -> 'PotConfig | None':
        try:
            with open(path, "r") as f:
                text = f.read()
        except FileNotFoundError:
            return None
            
        try:
            json_object = json.loads(text)
            pot_config: PotConfig = pydantic.TypeAdapter(PotConfig).validate_python(json_object)
            return pot_config
        except Exception as e:
            print(f"Error loading pot config: {e}")
            return None
            
    def save_to_file(self, path: str = DEFAULT_POT_CONFIG_PATH) -> bool:
        try:
            with open(path, "w") as f:
                f.write(self.model_dump_json())
            return True
        except Exception as e:
            print(f"Error saving pot config: {e}")
            return False
    