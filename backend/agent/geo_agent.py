from agents import Agent, set_default_openai_client
from openai import AsyncOpenAI

from backend.agent.system_prompt import SYSTEM_PROMPT
from backend.config import settings
from backend.tools import (
    catchment_area,
    compare_zones,
    find_zones,
    home_work_flow,
    roaming_analysis,
    zone_demographics,
    zone_traffic,
)
from backend.tools.base import GeoContext

# Point Agents SDK at vLLM
_client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)
set_default_openai_client(_client)

geo_agent = Agent[GeoContext](
    name="GeoInsight",
    model=settings.llm_model,
    instructions=SYSTEM_PROMPT,
    tools=[
        find_zones,
        zone_demographics,
        zone_traffic,
        home_work_flow,
        catchment_area,
        compare_zones,
        roaming_analysis,
    ],
)
