import pytest

from ai_perf.tool_catalogue import build_tool_specs, execute_tool


def test_catalogue_count_and_description_styles() -> None:
    minimal = build_tool_specs(5, "minimal")
    verbose = build_tool_specs(5, "verbose")

    assert len(minimal) == 5
    assert minimal[0].name == "lookup_weather"
    assert len(verbose[0].description) > len(minimal[0].description)


def test_catalogue_schema_styles_are_strict() -> None:
    many_parameters = build_tool_specs(5, schema_style="many_parameters")
    nested = build_tool_specs(5, schema_style="nested")

    many_schema = many_parameters[0].input_schema
    nested_schema = nested[0].input_schema
    assert many_schema["additionalProperties"] is False
    assert set(many_schema["required"]) == set(many_schema["properties"])
    assert nested_schema["properties"]["options"]["additionalProperties"] is False
    assert nested_schema["properties"]["options"]["required"] == ["locale", "units"]


def test_ambiguous_catalogue_uses_overlapping_descriptions() -> None:
    tools = build_tool_specs(2, ambiguous=True)

    assert tools[0].description == tools[1].description


def test_weather_tool_is_deterministic() -> None:
    assert execute_tool("lookup_weather", {"query": "Paris"}) == {
        "city": "Paris",
        "temperature_c": 21,
        "condition": "sunny",
    }


def test_tool_rejects_missing_query() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        execute_tool("lookup_weather", {})
