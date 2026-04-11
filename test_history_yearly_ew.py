import importlib
import sys
import types

import pandas as pd
import pytest

from history_analyzer import HistoryAnalyzer


@pytest.fixture(scope="module")
def analyzer():
    instance = HistoryAnalyzer(data_path="data/hangzhou_weather.csv")
    instance.load_data(force_reload=True)
    return instance


def install_app_stubs(monkeypatch):
    plotly_stub = types.ModuleType("plotly")
    graph_objects_stub = types.ModuleType("plotly.graph_objects")
    express_stub = types.ModuleType("plotly.express")
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None

    weather_service_stub = types.ModuleType("weather_service")
    weather_service_stub.WeatherService = type("WeatherService", (), {"__init__": lambda self, *args, **kwargs: None})

    ecmwf_service_stub = types.ModuleType("ecmwf_service")
    ecmwf_service_stub.ECMWFService = type("ECMWFService", (), {"__init__": lambda self, *args, **kwargs: None})

    advanced_service_stub = types.ModuleType("advanced_forecast_service")
    advanced_service_stub.AdvancedForecastService = type(
        "AdvancedForecastService",
        (),
        {
            "__init__": lambda self, *args, **kwargs: None,
            "fetch_detailed_72h_forecast": lambda self, *args, **kwargs: None,
            "fetch_multi_model_forecast": lambda self, *args, **kwargs: None,
        },
    )

    ml_correction_stub = types.ModuleType("ml_correction")
    ml_correction_stub.apply_ml_correction = lambda *args, **kwargs: args[0] if args else None
    ml_correction_stub.get_corrector = lambda *args, **kwargs: None

    sounding_parser_stub = types.ModuleType("sounding_parser")
    sounding_parser_stub.SoundingDataParser = type("SoundingDataParser", (), {"__init__": lambda self, *args, **kwargs: None})

    sounding_plotter_stub = types.ModuleType("sounding_plotter")
    sounding_plotter_stub.SoundingPlotter = type("SoundingPlotter", (), {"__init__": lambda self, *args, **kwargs: None})

    sounding_analyzer_stub = types.ModuleType("sounding_analyzer")
    sounding_analyzer_stub.SoundingAnalyzer = type("SoundingAnalyzer", (), {"__init__": lambda self, *args, **kwargs: None})

    crop_database_stub = types.ModuleType("crop_database")
    crop_database_stub.crop_db = object()

    agro_calculator_stub = types.ModuleType("agro_calculator")
    agro_calculator_stub.agro_calculator = object()

    agro_alert_stub = types.ModuleType("agro_alert_engine")
    agro_alert_stub.agro_alert_engine = object()

    farming_ai_stub = types.ModuleType("farming_ai_adviser")
    farming_ai_stub.ai_adviser = object()

    monkeypatch.setitem(sys.modules, "plotly", plotly_stub)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", graph_objects_stub)
    monkeypatch.setitem(sys.modules, "plotly.express", express_stub)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv_stub)
    monkeypatch.setitem(sys.modules, "weather_service", weather_service_stub)
    monkeypatch.setitem(sys.modules, "ecmwf_service", ecmwf_service_stub)
    monkeypatch.setitem(sys.modules, "advanced_forecast_service", advanced_service_stub)
    monkeypatch.setitem(sys.modules, "ml_correction", ml_correction_stub)
    monkeypatch.setitem(sys.modules, "sounding_parser", sounding_parser_stub)
    monkeypatch.setitem(sys.modules, "sounding_plotter", sounding_plotter_stub)
    monkeypatch.setitem(sys.modules, "sounding_analyzer", sounding_analyzer_stub)
    monkeypatch.setitem(sys.modules, "crop_database", crop_database_stub)
    monkeypatch.setitem(sys.modules, "agro_calculator", agro_calculator_stub)
    monkeypatch.setitem(sys.modules, "agro_alert_engine", agro_alert_stub)
    monkeypatch.setitem(sys.modules, "farming_ai_adviser", farming_ai_stub)


def load_app_module(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    install_app_stubs(monkeypatch)
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_same_calendar_day_sample_sizes(analyzer):
    daily = analyzer._build_daily_event_metrics(analyzer.data)
    sample_715 = daily[(daily["month"] == 7) & (daily["day"] == 15)]
    sample_229 = daily[(daily["month"] == 2) & (daily["day"] == 29)]

    assert len(sample_715) >= 18
    assert len(sample_229) == 5


def test_low_temperature_uses_reverse_percentile(analyzer):
    daily = analyzer._build_daily_event_metrics(analyzer.data)
    sample = daily[(daily["month"] == 2) & (daily["day"] == 18)]["temp_min"].dropna()

    cold_value = float(sample.min())
    mild_value = float(sample.max())

    cold_percentile, cold_size = analyzer._compute_empirical_percentile(cold_value, sample)
    mild_percentile, mild_size = analyzer._compute_empirical_percentile(mild_value, sample)

    assert cold_size == mild_size >= 5
    assert (1 - cold_percentile) > (1 - mild_percentile)


def test_ew_process_deduplicates_continuous_days(analyzer):
    candidates = [
        {
            "season": "冬季",
            "date_obj": pd.Timestamp("2021-01-01").date(),
            "peak_date": "2021-01-01",
            "type": "极端低温",
            "value": "-5.8°C",
            "ew_score": 0.97,
            "primary_metric": "日最低温",
            "sample_size": 18,
            "season_gate": 2.0,
        },
        {
            "season": "冬季",
            "date_obj": pd.Timestamp("2021-01-02").date(),
            "peak_date": "2021-01-02",
            "type": "极端低温",
            "value": "-5.2°C",
            "ew_score": 0.96,
            "primary_metric": "日最低温",
            "sample_size": 18,
            "season_gate": 2.0,
        },
        {
            "season": "冬季",
            "date_obj": pd.Timestamp("2021-01-07").date(),
            "peak_date": "2021-01-07",
            "type": "极端低温",
            "value": "-4.6°C",
            "ew_score": 0.95,
            "primary_metric": "日最低温",
            "sample_size": 18,
            "season_gate": 2.0,
        },
    ]

    processes = analyzer._build_ew_processes(candidates, max_gap_days=2)

    assert len(processes) == 2
    assert processes[0]["peak_date"] == "2021-01-01"
    assert processes[0]["duration_days"] == 2
    assert processes[1]["start_date"] == "2021-01-07"


def test_analyze_year_returns_seasonal_ew_groups_without_wind(analyzer):
    result = analyzer.analyze_year(2021)

    assert result["extremes"] == result["extremes_raw"]
    assert set(result["extremes_ew_by_season"].keys()) == {"春季", "夏季", "秋季", "冬季"}

    flattened = result["extremes_ew_summary"]
    assert flattened == result["extremes_ew"]
    assert all(event["primary_metric"] != "日最大阵风" for event in flattened)
    assert all(event["season"] in {"春季", "夏季", "秋季", "冬季"} for event in flattened)
    assert all(event["duration_days"] >= 1 for event in flattened)

    for season_events in result["extremes_ew_by_season"].values():
        assert len(season_events) <= 3

    winter_low_temp_events = [
        event for event in result["extremes_ew_by_season"]["冬季"]
        if event["primary_metric"] == "日最低温"
    ]
    assert len(winter_low_temp_events) <= 1


def test_history_yearly_page_renders_seasonal_ew_sections(monkeypatch):
    weather_app = load_app_module(monkeypatch)

    monkeypatch.setattr(weather_app, "get_ai_analysis", lambda prompt: "<p>stub</p>")
    monkeypatch.setattr(weather_app.ChartGenerator, "create_monthly_comparison_chart", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(weather_app.ChartGenerator, "create_daily_temp_distribution", staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(weather_app.ChartGenerator, "create_wind_rose_chart", staticmethod(lambda *args, **kwargs: None))

    client = weather_app.app.test_client()
    response = client.get("/history/yearly/2021?climatology=8110")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "原始极值" in html
    assert "EW 指数" in html
    assert "春季代表事件" in html
    assert "夏季代表事件" in html
    assert "每季每要素最多保留 1 个代表过程" in html


def test_upperair_request_time_is_converted_from_china_time(monkeypatch):
    weather_app = load_app_module(monkeypatch)

    parsed = weather_app._parse_upperair_request_time("2026-04-10 08:00")

    assert parsed["requested_time_local"].strftime("%Y-%m-%d %H:%M %Z") == "2026-04-10 08:00 CST"
    assert parsed["requested_time_utc"].strftime("%Y-%m-%d %H:%M UTC") == "2026-04-10 00:00 UTC"
    assert parsed["target_time_utc"].strftime("%Y-%m-%d %H:%M UTC") == "2026-04-10 00:00 UTC"


def test_upperair_data_route_returns_metadata_and_cape_na(monkeypatch):
    weather_app = load_app_module(monkeypatch)

    monkeypatch.setattr(
        weather_app.sounding_parser,
        "fetch_sounding_data",
        lambda station_id, target_time: {
            "success": True,
            "raw_data": "stub",
            "resolved_time_utc": "2026-04-10 00:00 UTC",
            "fallback_used": True,
        },
        raising=False,
    )
    monkeypatch.setattr(
        weather_app.sounding_parser,
        "parse_sounding_data",
        lambda raw_data: {
            "header": {"station_id": "58457", "time_utc": "00Z 10 Apr 2026", "station_name": "HANGZHOU, China"},
            "levels": [{"PRES": 1000.0, "HGHT": 43.0, "TEMP": 20.0, "DWPT": 18.0, "RELH": 90.0, "DRCT": 180.0, "SPED": 5.0}],
            "indices": {},
        },
        raising=False,
    )
    monkeypatch.setattr(weather_app.sounding_parser, "save_to_csv", lambda *args, **kwargs: True, raising=False)
    monkeypatch.setattr(
        weather_app.sounding_analyzer,
        "analyze",
        lambda df, indices: {
            "parameters": {
                "cape": "N/A",
                "cin": -50.0,
                "k_index": 20.0,
                "lifted_index": "N/A",
                "shear_06km": 10.0,
                "precip_water": 30.0,
            },
            "risk_assessment": {"level": "低", "color": "success", "description": "稳定", "hazards": []},
            "layer_data": {},
            "ai_analysis": {"professional": "stub", "simple": "stub", "impacts": {}},
        },
        raising=False,
    )

    client = weather_app.app.test_client()
    response = client.get("/upperair/data?date=2026-04-10%2008:00")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["parameters"]["cape"] == "N/A"
    assert payload["data"]["metadata"]["requested_time_local"] == "2026-04-10 08:00 CST"
    assert payload["data"]["metadata"]["requested_time_utc"] == "2026-04-10 00:00 UTC"
    assert payload["data"]["metadata"]["resolved_time_utc"] == "2026-04-10 00:00 UTC"
    assert payload["data"]["metadata"]["fallback_used"] is True
