from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


DeviceId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=40,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]

class SensorData(BaseModel):
    device_id: DeviceId
    temperature: float = Field(ge=-50, le=250, allow_inf_nan=False)
    vibration: float = Field(ge=0, le=50, allow_inf_nan=False)


LocationName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=120,
    ),
]

class DeviceDiscovery(BaseModel):
    device_id: DeviceId
    device_type: str = Field(default="Industrial Sensor", min_length=3, max_length=80)
    location: LocationName | None = None
