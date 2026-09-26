from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

DescriptionStyle = Literal["minimal", "concise", "verbose"]
SchemaStyle = Literal["simple", "many_parameters", "nested"]

TOOL_NAMES = (
    "lookup_weather",
    "get_local_time",
    "search_customer_orders",
    "lookup_product_inventory",
    "calculate_shipping_quote",
    "get_exchange_rate",
    "search_support_articles",
    "lookup_account_balance",
    "schedule_meeting",
    "find_nearby_store",
    "lookup_flight_status",
    "calculate_sales_tax",
    "search_employee_directory",
    "get_package_tracking",
    "lookup_subscription_status",
    "search_product_catalog",
    "calculate_loan_payment",
    "get_service_health",
    "lookup_invoice_status",
    "search_training_courses",
    "get_energy_usage",
    "lookup_vehicle_service",
    "calculate_discount",
    "search_legal_policies",
    "get_build_status",
    "lookup_hotel_booking",
    "calculate_currency_total",
    "search_code_repository",
    "get_database_health",
    "lookup_asset_owner",
    "calculate_route_distance",
    "search_marketing_campaigns",
    "get_network_latency",
    "lookup_purchase_request",
    "calculate_inventory_turnover",
    "search_security_alerts",
    "get_certificate_expiry",
    "lookup_vendor_profile",
    "calculate_storage_cost",
    "search_release_notes",
    "get_queue_depth",
    "lookup_contract_status",
    "calculate_project_burn",
    "search_incident_history",
    "get_api_quota",
    "lookup_device_compliance",
    "calculate_carbon_estimate",
    "search_architecture_decisions",
    "get_backup_status",
    "lookup_cost_center",
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
            "strict": True,
        }


def _description(name: str, style: DescriptionStyle, *, ambiguous: bool) -> str:
    readable = name.replace("_", " ")
    if style == "minimal":
        return readable.capitalize()
    if ambiguous and name in {"lookup_weather", "get_local_time"}:
        concise = "Return current benchmark information for a city."
    elif name == "lookup_weather":
        concise = "Return the benchmark temperature for a city. Use only for weather questions."
    elif name == "get_local_time":
        concise = "Return the benchmark local time for a city. Use only for time questions."
    else:
        concise = f"Use {readable} for requests specifically about {readable}."
    if style == "concise":
        return concise
    return (
        f"{concise} This tool is part of the AI performance benchmark catalogue. "
        "Call it only when the user's request clearly matches this capability, provide the "
        "complete query as a string, and do not select it for adjacent or unrelated domains."
    )


def _input_schema(style: SchemaStyle) -> dict[str, Any]:
    if style == "simple":
        properties: dict[str, Any] = {
            "query": {"type": "string", "description": "City or lookup query."}
        }
    elif style == "many_parameters":
        properties = {
            "query": {"type": "string", "description": "City or lookup query."},
            "locale": {"type": "string", "description": "Response locale such as en-US."},
            "units": {
                "type": "string",
                "enum": ["metric", "imperial"],
                "description": "Measurement system.",
            },
            "include_metadata": {
                "type": "boolean",
                "description": "Whether to include benchmark metadata.",
            },
            "result_limit": {
                "type": "integer",
                "description": "Maximum number of results.",
            },
        }
    elif style == "nested":
        properties = {
            "query": {"type": "string", "description": "City or lookup query."},
            "options": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "locale": {"type": "string"},
                    "units": {"type": "string", "enum": ["metric", "imperial"]},
                },
                "required": ["locale", "units"],
            },
        }
    else:
        raise ValueError(f"Unsupported schema style: {style}")

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def build_tool_specs(
    count: int,
    style: DescriptionStyle = "concise",
    *,
    schema_style: SchemaStyle = "simple",
    ambiguous: bool = False,
) -> list[ToolSpec]:
    if not 1 <= count <= len(TOOL_NAMES):
        raise ValueError(f"tool count must be between 1 and {len(TOOL_NAMES)}")
    schema = _input_schema(schema_style)
    return [
        ToolSpec(
            name=name,
            description=_description(name, style, ambiguous=ambiguous),
            input_schema=schema,
        )
        for name in TOOL_NAMES[:count]
    ]


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError(f"{name} requires a non-empty string query")
    if name == "lookup_weather":
        return {"city": query, "temperature_c": 21, "condition": "sunny"}
    if name == "get_local_time":
        return {"city": query, "local_time": "14:30"}
    return {"tool": name, "query": query, "result": "benchmark-result"}


def serialize_tool_result(result: dict[str, Any]) -> str:
    return json.dumps(result, separators=(",", ":"), sort_keys=True)
