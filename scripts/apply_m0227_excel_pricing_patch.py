from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VBA_PATH = PROJECT_ROOT / "vba" / "FybrocApiClient.bas"
BACKUP_DIR = PROJECT_ROOT / "backups" / "M0227"

MARKER = "' M022.7 - Fybroc API component pricing bridge."

HELPER_BLOCK = r'''
' M022.7 - Fybroc API component pricing bridge.
'
' Pricing remains server-authored. The workbook receives only the component
' amounts returned by the finalize response:
'   BASE_PUMP -> Price Check!Q80
'   SEAL      -> Price Check!Q81
'
' Q80/Q81 are the workbook's existing list-price override inputs. D80/D81,
' F80/F81, D102/F102, and Formal Quote formulas are intentionally preserved.
Private Sub WritePricingResponse(ByVal responseObject As Object)
    Dim pricingObject As Object
    Set pricingObject = JsonObjectChildObject(responseObject, "pricing")

    If pricingObject Is Nothing Then
        Err.Raise vbObjectError + 2060, , _
            "The API finalize response did not include the pricing object."
    End If

    Dim pricingStatus As String
    pricingStatus = LCase$(Trim$(JsonObjectText(pricingObject, "status")))

    WriteNamedValue "API_PricingStatus", pricingStatus
    WriteNamedValue "API_TotalAmount", _
        JsonObjectValue(pricingObject, "totalAmount")
    WriteNamedValue "API_KnownAmount", _
        JsonObjectValue(pricingObject, "knownAmount")
    WriteNamedValue "API_CurrencyCode", _
        JsonObjectText(pricingObject, "currencyCode")

    WriteNamedValue "API_BasePumpAmount", 0
    WriteNamedValue "API_SealAmount", 0

    Dim priceSheet As Worksheet
    Set priceSheet = ThisWorkbook.Worksheets("Price Check")

    priceSheet.Range("Q80").Value2 = 0
    priceSheet.Range("Q81").Value2 = 0

    Dim components As Collection
    Set components = pricingObject("components")

    Dim item As Variant
    Dim componentCode As String
    Dim componentStatus As String
    Dim amountValue As Variant

    For Each item In components
        componentCode = UCase$(Trim$( _
            JsonObjectText(item, "componentCode") _
        ))
        componentStatus = LCase$(Trim$( _
            JsonObjectText(item, "status") _
        ))

        If componentStatus = "found" Then
            amountValue = JsonObjectValue(item, "amount")
        Else
            amountValue = 0
        End If

        Select Case componentCode
            Case "BASE_PUMP"
                WriteNamedValue "API_BasePumpAmount", amountValue
                priceSheet.Range("Q80").Value2 = amountValue

            Case "SEAL"
                WriteNamedValue "API_SealAmount", amountValue
                priceSheet.Range("Q81").Value2 = amountValue
        End Select
    Next item
End Sub

Private Sub ClearApiPricingBridge()
    On Error Resume Next

    WriteNamedValue "API_PricingStatus", vbNullString
    WriteNamedValue "API_TotalAmount", vbNullString
    WriteNamedValue "API_KnownAmount", vbNullString
    WriteNamedValue "API_CurrencyCode", vbNullString
    WriteNamedValue "API_BasePumpAmount", vbNullString
    WriteNamedValue "API_SealAmount", vbNullString

    With ThisWorkbook.Worksheets("Price Check")
        .Range("Q80:Q81").ClearContents
    End With

    On Error GoTo 0
End Sub

Private Sub CalculateApiBridge()
    ' Keep calculation targeted. A full workbook rebuild is intentionally
    ' avoided because this legacy workbook contains existing VBA/UDF logic.
    With ThisWorkbook.Worksheets("Price Check")
        .Range("F5").Calculate
        .Range("D80:G81").Calculate
        .Range("D102:G102").Calculate
    End With

    With ThisWorkbook.Worksheets("Formal Quote")
        .Range("I23").Calculate
        .Range("AB23").Calculate
        .Range("AM48").Calculate
        .Range("Q44:Q47").Calculate
    End With
End Sub

Private Function JsonObjectChildObject( _
    ByVal obj As Object, _
    ByVal keyText As String _
) As Object
    On Error GoTo MissingObject

    Set JsonObjectChildObject = obj(keyText)
    Exit Function

MissingObject:
    Set JsonObjectChildObject = Nothing
End Function

'''


def require_count(text: str, needle: str, expected: int, label: str) -> None:
    actual = text.count(needle)
    if actual != expected:
        raise RuntimeError(
            f"{label}: expected {expected} anchor occurrence(s), found {actual}. "
            "No source file was written."
        )


def replace_once(text: str, old: str, new: str, label: str) -> str:
    require_count(text, old, 1, label)
    return text.replace(old, new, 1)


def patch_vba_text(text: str) -> str:
    if MARKER in text:
        return text

    old_reset = (
        "    ClearApiResultValues\r\n"
        "    ClearOptionTable\r\n"
        "    RemoveOptionValidation\r\n"
    )
    new_reset = (
        "    ClearApiResultValues\r\n"
        "    ClearApiPricingBridge\r\n"
        "    ClearOptionTable\r\n"
        "    RemoveOptionValidation\r\n"
    )
    require_count(text, old_reset, 2, "start/clear pricing reset")
    text = text.replace(old_reset, new_reset)

    text = replace_once(
        text,
        '    WriteNamedValue "API_RuntimeRevision", _\r\n'
        '        JsonObjectText(responseObject, "runtimeRevision")\r\n'
        '    WriteNamedValue "API_Status", "finalized"\r\n',
        '    WriteNamedValue "API_RuntimeRevision", _\r\n'
        '        JsonObjectText(responseObject, "runtimeRevision")\r\n'
        "\r\n"
        "    WritePricingResponse responseObject\r\n"
        "\r\n"
        '    WriteNamedValue "API_Status", "finalized"\r\n',
        "finalize pricing writeback",
    )

    old_calc = (
        '    ThisWorkbook.Worksheets("Price Check").Range("F5").Calculate\r\n'
    )
    require_count(text, old_calc, 2, "targeted F5 calculation")
    text = text.replace(old_calc, "    CalculateApiBridge\r\n")

    anchor = "Private Sub ClearApiResultValues()\r\n"
    text = replace_once(
        text,
        anchor,
        HELPER_BLOCK.replace("\n", "\r\n") + anchor,
        "M022.7 helper insertion",
    )

    return text


def main() -> int:
    if not VBA_PATH.exists():
        raise FileNotFoundError(f"Missing VBA module: {VBA_PATH}")

    original_bytes = VBA_PATH.read_bytes()

    try:
        original = original_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        original = original_bytes.decode("cp1252")

    normalized = (
        original
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\r\n")
    )

    patched = patch_vba_text(normalized)

    if patched == normalized:
        print("=" * 88)
        print("M022.7 VBA SOURCE ALREADY PATCHED")
        print("=" * 88)
        print(f"Source: {VBA_PATH}")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = (
        BACKUP_DIR
        / f"FybrocApiClient_before_m0227_{stamp}.bas"
    )
    shutil.copy2(VBA_PATH, backup_path)

    VBA_PATH.write_text(
        patched.replace("\r\n", "\n"),
        encoding="utf-8",
        newline="\n",
    )

    print("=" * 88)
    print("M022.7 FYBROC VBA SOURCE PATCH APPLIED")
    print("=" * 88)
    print(f"Updated : {VBA_PATH}")
    print(f"Backup  : {backup_path}")
    print("Bridge  : BASE_PUMP -> Price Check!Q80")
    print("Bridge  : SEAL      -> Price Check!Q81")
    print("Reset   : Start and Clear both remove stale Q80/Q81 API prices")
    print("Totals  : Existing D/F and Formal Quote formulas preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
