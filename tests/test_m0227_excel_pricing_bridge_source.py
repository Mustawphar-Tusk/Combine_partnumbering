from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VBA_PATH = PROJECT_ROOT / "vba" / "FybrocApiClient.bas"


def _source() -> str:
    return VBA_PATH.read_text(encoding="utf-8", errors="replace")


def test_m0227_component_pricing_bridge_is_present():
    text = _source()
    assert "M022.7 - Fybroc API component pricing bridge." in text
    assert "WritePricingResponse responseObject" in text
    assert '"BASE_PUMP"' in text
    assert '"SEAL"' in text
    assert 'Range("Q80").Value2 = amountValue' in text
    assert 'Range("Q81").Value2 = amountValue' in text


def test_m0227_clears_stale_pricing_overrides():
    text = _source()
    assert text.count("ClearApiPricingBridge") >= 3
    assert '.Range("Q80:Q81").ClearContents' in text


def test_m0227_keeps_targeted_calculation():
    text = _source()
    assert "Private Sub CalculateApiBridge()" in text
    assert '.Range("D80:G81").Calculate' in text
    assert '.Range("D102:G102").Calculate' in text
    assert '.Range("I23").Calculate' in text
