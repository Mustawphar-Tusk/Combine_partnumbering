Attribute VB_Name = "FybrocApiClient"
Option Explicit

' M020.4 - Closed Fybroc Excel API client.
'
' Security model:
' - The workbook never sends arbitrary engineering field/value pairs.
' - It sends only server-issued stateToken and optionToken values.
' - CONFIGURATION_TOKEN_SECRET remains server-side.

Private Const UI_SHEET As String = "API Configurator"

Private Const CELL_API_URL As String = "B3"
Private Const CELL_FAMILY As String = "B4"
Private Const CELL_CURRENT_FIELD As String = "B6"
Private Const CELL_SELECTION_COUNT As String = "B7"
Private Const CELL_STATUS As String = "B8"
Private Const CELL_SELECTED_OPTION As String = "B10"
Private Const CELL_PART_NUMBER As String = "B12"
Private Const CELL_SKU As String = "B13"
Private Const CELL_REGISTRY_ID As String = "B14"

Private Const OPTION_FIRST_ROW As Long = 2
Private Const OPTION_LAST_ROW As Long = 500
Private Const OPTION_DISPLAY_COLUMN As String = "H"
Private Const OPTION_TOKEN_COLUMN As String = "I"

Private mJsonText As String
Private mJsonPosition As Long

Public Sub Fybroc_StartConfiguration()
    On Error GoTo HandleError

    Dim ui As Worksheet
    Set ui = ApiUiSheet()

    Dim baseUrl As String
    baseUrl = NormalizeBaseUrl(CStr(ui.Range(CELL_API_URL).Value2))

    Dim familyCode As String
    familyCode = UCase$(Trim$(CStr(ui.Range(CELL_FAMILY).Value2)))

    If Len(baseUrl) = 0 Then
        Err.Raise vbObjectError + 2000, , "Enter the API base URL."
    End If

    If Len(familyCode) = 0 Then
        Err.Raise vbObjectError + 2001, , "Enter a family code."
    End If

    ClearApiResultValues
    ClearOptionTable
    RemoveOptionValidation

    ui.Range(CELL_CURRENT_FIELD).ClearContents
    ui.Range(CELL_SELECTION_COUNT).Value = 0
    ui.Range(CELL_SELECTED_OPTION).ClearContents
    ui.Range(CELL_PART_NUMBER).ClearContents
    ui.Range(CELL_SKU).ClearContents
    ui.Range(CELL_REGISTRY_ID).ClearContents
    ui.Range(CELL_STATUS).Value = "Starting configuration..."
    DoEvents

    Dim responseText As String
    responseText = HttpPostJson( _
        baseUrl & "/api/v1/families/" & UrlEncode(familyCode) & _
        "/configurations/start", _
        "{}", _
        vbNullString _
    )

    Dim responseObject As Object
    Set responseObject = JsonParseObject(responseText)

    ApplyNavigationResponse responseObject
    ThisWorkbook.Save
    Exit Sub

HandleError:
    ShowApiError "Start configuration", Err.Number, Err.Description
End Sub

Public Sub Fybroc_AdvanceConfiguration()
    On Error GoTo HandleError

    Dim ui As Worksheet
    Set ui = ApiUiSheet()

    Dim selectedDisplayValue As String
    selectedDisplayValue = Trim$(CStr(ui.Range(CELL_SELECTED_OPTION).Value2))

    If Len(selectedDisplayValue) = 0 Then
        Err.Raise vbObjectError + 2010, , _
            "Select one of the allowable options."
    End If

    Dim optionToken As String
    optionToken = FindOptionToken(selectedDisplayValue)

    If Len(optionToken) = 0 Then
        Err.Raise vbObjectError + 2011, , _
            "The selected value does not have a current server-issued option token."
    End If

    Dim stateToken As String
    stateToken = CStr(ThisWorkbook.Names("API_StateToken").RefersToRange.Value2)

    If Len(stateToken) = 0 Then
        Err.Raise vbObjectError + 2012, , _
            "No signed configuration state is available. Start a configuration first."
    End If

    Dim baseUrl As String
    baseUrl = NormalizeBaseUrl(CStr(ui.Range(CELL_API_URL).Value2))

    Dim familyCode As String
    familyCode = UCase$(Trim$(CStr(ui.Range(CELL_FAMILY).Value2)))

    ui.Range(CELL_STATUS).Value = "Applying allowable option..."
    DoEvents

    Dim requestBody As String
    requestBody = "{""stateToken"":""" & JsonEscape(stateToken) & _
                  """,""optionToken"":""" & JsonEscape(optionToken) & """}"

    Dim responseText As String
    responseText = HttpPostJson( _
        baseUrl & "/api/v1/families/" & UrlEncode(familyCode) & _
        "/configurations/advance", _
        requestBody, _
        vbNullString _
    )

    Dim responseObject As Object
    Set responseObject = JsonParseObject(responseText)

    ApplyNavigationResponse responseObject
    ThisWorkbook.Save
    Exit Sub

HandleError:
    ShowApiError "Advance configuration", Err.Number, Err.Description
End Sub

Public Sub Fybroc_FinalizeConfiguration()
    On Error GoTo HandleError

    Dim ui As Worksheet
    Set ui = ApiUiSheet()

    Dim stateToken As String
    stateToken = CStr(ThisWorkbook.Names("API_StateToken").RefersToRange.Value2)

    If Len(stateToken) = 0 Then
        Err.Raise vbObjectError + 2020, , _
            "No signed configuration state is available."
    End If

    If LCase$(Trim$(CStr(ThisWorkbook.Names("API_Status").RefersToRange.Value2))) <> "complete" Then
        Err.Raise vbObjectError + 2021, , _
            "Complete every allowable configuration field before finalizing."
    End If

    Dim baseUrl As String
    baseUrl = NormalizeBaseUrl(CStr(ui.Range(CELL_API_URL).Value2))

    Dim familyCode As String
    familyCode = UCase$(Trim$(CStr(ui.Range(CELL_FAMILY).Value2)))

    ui.Range(CELL_STATUS).Value = "Finalizing and persisting..."
    DoEvents

    Dim requestBody As String
    requestBody = "{""stateToken"":""" & JsonEscape(stateToken) & """}"

    Dim requestedBy As String
    requestedBy = "excel:" & Environ$("USERNAME")

    Dim responseText As String
    responseText = HttpPostJson( _
        baseUrl & "/api/v1/families/" & UrlEncode(familyCode) & _
        "/configurations/finalize", _
        requestBody, _
        requestedBy _
    )

    Dim responseObject As Object
    Set responseObject = JsonParseObject(responseText)

    WriteNamedValue "API_PartNumber", JsonObjectText(responseObject, "partNumber")
    WriteNamedValue "API_SKU", JsonObjectText(responseObject, "sku")
    WriteNamedValue "API_ConfigurationSignature", _
        JsonObjectText(responseObject, "configurationSignature")
    WriteNamedValue "API_ConfiguredProductRegistryId", _
        JsonObjectValue(responseObject, "configuredProductRegistryId")
    WriteNamedValue "API_WasCreated", _
        JsonObjectValue(responseObject, "wasCreated")
    WriteNamedValue "API_RequestCount", _
        JsonObjectValue(responseObject, "requestCount")
    WriteNamedValue "API_RuntimeRevision", _
        JsonObjectText(responseObject, "runtimeRevision")
    WriteNamedValue "API_Status", "finalized"
    WriteNamedValue "API_LastUpdatedUtc", Format$(Now, "yyyy-mm-dd\Thh:nn:ss")

    ui.Range(CELL_PART_NUMBER).Value = _
        JsonObjectText(responseObject, "partNumber")
    ui.Range(CELL_SKU).Value = _
        JsonObjectText(responseObject, "sku")
    ui.Range(CELL_REGISTRY_ID).Value = _
        JsonObjectValue(responseObject, "configuredProductRegistryId")

    If CBool(JsonObjectValue(responseObject, "wasCreated")) Then
        ui.Range(CELL_STATUS).Value = _
            "Finalized - new configured product created"
    Else
        ui.Range(CELL_STATUS).Value = _
            "Finalized - existing configured product reused"
    End If

    ' Calculate only the API bridge cell. Do not run a full workbook rebuild,
    ' because this legacy workbook contains existing VBA/UDF logic.
    ThisWorkbook.Worksheets("Price Check").Range("F5").Calculate

    ThisWorkbook.Save

    MsgBox _
        "Configuration finalized successfully." & vbCrLf & vbCrLf & _
        "Part Number: " & JsonObjectText(responseObject, "partNumber") & vbCrLf & _
        "SKU: " & JsonObjectText(responseObject, "sku"), _
        vbInformation, _
        "Fybroc Pump Configurator"

    Exit Sub

HandleError:
    ShowApiError "Finalize configuration", Err.Number, Err.Description
End Sub

Public Sub Fybroc_ClearApiResult()
    On Error GoTo HandleError

    If MsgBox( _
        "Clear the API-generated part number, SKU, and current signed session?", _
        vbQuestion + vbYesNo, _
        "Clear API Configuration" _
    ) <> vbYes Then
        Exit Sub
    End If

    ClearApiResultValues
    ClearOptionTable
    RemoveOptionValidation

    Dim ui As Worksheet
    Set ui = ApiUiSheet()

    ui.Range(CELL_CURRENT_FIELD).ClearContents
    ui.Range(CELL_SELECTION_COUNT).Value = 0
    ui.Range(CELL_STATUS).Value = "Ready"
    ui.Range(CELL_SELECTED_OPTION).ClearContents
    ui.Range(CELL_PART_NUMBER).ClearContents
    ui.Range(CELL_SKU).ClearContents
    ui.Range(CELL_REGISTRY_ID).ClearContents

    ThisWorkbook.Worksheets("Price Check").Range("F5").Calculate
    ThisWorkbook.Save
    Exit Sub

HandleError:
    ShowApiError "Clear API result", Err.Number, Err.Description
End Sub

Private Sub ApplyNavigationResponse(ByVal responseObject As Object)
    Dim ui As Worksheet
    Set ui = ApiUiSheet()

    Dim stateToken As String
    stateToken = JsonObjectText(responseObject, "stateToken")

    Dim nextFieldCode As String
    nextFieldCode = JsonObjectText(responseObject, "nextFieldCode")

    Dim selectionCount As Variant
    selectionCount = JsonObjectValue(responseObject, "selectionCount")

    Dim isComplete As Boolean
    isComplete = CBool(JsonObjectValue(responseObject, "complete"))

    WriteNamedValue "API_StateToken", stateToken
    WriteNamedValue "API_RuntimeRevision", _
        JsonObjectText(responseObject, "runtimeRevision")
    WriteNamedValue "API_Status", IIf(isComplete, "complete", "in_progress")
    WriteNamedValue "API_LastUpdatedUtc", Format$(Now, "yyyy-mm-dd\Thh:nn:ss")

    ui.Range(CELL_CURRENT_FIELD).Value = nextFieldCode
    ui.Range(CELL_SELECTION_COUNT).Value = selectionCount
    ui.Range(CELL_SELECTED_OPTION).ClearContents

    ClearOptionTable
    RemoveOptionValidation

    If isComplete Then
        ui.Range(CELL_STATUS).Value = _
            "Complete - ready to finalize"
        Exit Sub
    End If

    Dim options As Collection
    Set options = responseObject("options")

    Dim rowNumber As Long
    rowNumber = OPTION_FIRST_ROW

    Dim item As Variant
    For Each item In options
        ui.Range(OPTION_DISPLAY_COLUMN & rowNumber).Value = _
            JsonObjectText(item, "displayValue")
        ui.Range(OPTION_TOKEN_COLUMN & rowNumber).NumberFormat = "@"
        ui.Range(OPTION_TOKEN_COLUMN & rowNumber).Value = _
            JsonObjectText(item, "optionToken")
        rowNumber = rowNumber + 1
    Next item

    If rowNumber = OPTION_FIRST_ROW Then
        Err.Raise vbObjectError + 2030, , _
            "The API returned no allowable options for the current state."
    End If

    ApplyOptionValidation rowNumber - 1

    ui.Range(CELL_STATUS).Value = _
        "Choose an allowable value for " & nextFieldCode
End Sub

Private Function HttpPostJson( _
    ByVal url As String, _
    ByVal requestBody As String, _
    ByVal requestedBy As String _
) As String

    On Error GoTo HandleError

    Dim request As Object
    Set request = CreateObject("WinHttp.WinHttpRequest.5.1")

    request.SetTimeouts 5000, 5000, 30000, 30000
    request.Open "POST", url, False
    request.SetRequestHeader "Content-Type", "application/json"
    request.SetRequestHeader "Accept", "application/json"

    If Len(requestedBy) > 0 Then
        request.SetRequestHeader "X-Requested-By", requestedBy
    End If

    request.Send requestBody

    If request.Status < 200 Or request.Status >= 300 Then
        Err.Raise vbObjectError + 2040, , _
            "HTTP " & request.Status & " " & request.StatusText & vbCrLf & _
            CStr(request.ResponseText)
    End If

    HttpPostJson = CStr(request.ResponseText)
    Exit Function

HandleError:
    If Err.Number = -2147012894 Or Err.Number = -2147012867 Then
        Err.Raise vbObjectError + 2041, , _
            "The local Pump Configuration API is not reachable. " & _
            "Start Uvicorn at http://127.0.0.1:8000 and try again."
    End If

    Err.Raise Err.Number, Err.Source, Err.Description
End Function

Private Function FindOptionToken(ByVal displayValue As String) As String
    Dim ui As Worksheet
    Set ui = ApiUiSheet()

    Dim rowNumber As Long
    For rowNumber = OPTION_FIRST_ROW To OPTION_LAST_ROW
        If CStr(ui.Range(OPTION_DISPLAY_COLUMN & rowNumber).Value2) = displayValue Then
            FindOptionToken = _
                CStr(ui.Range(OPTION_TOKEN_COLUMN & rowNumber).Value2)
            Exit Function
        End If
    Next rowNumber
End Function

Private Sub ApplyOptionValidation(ByVal lastOptionRow As Long)
    Dim target As Range
    Set target = ApiUiSheet().Range(CELL_SELECTED_OPTION)

    target.Validation.Delete
    target.Validation.Add _
        Type:=xlValidateList, _
        AlertStyle:=xlValidAlertStop, _
        Operator:=xlBetween, _
        Formula1:="=$" & OPTION_DISPLAY_COLUMN & "$" & OPTION_FIRST_ROW & _
                 ":$" & OPTION_DISPLAY_COLUMN & "$" & lastOptionRow

    target.Validation.IgnoreBlank = True
    target.Validation.InCellDropdown = True
    target.Validation.ShowError = True
    target.Validation.ErrorTitle = "Allowable option required"
    target.Validation.ErrorMessage = _
        "Choose one of the values returned by the configuration API."
End Sub

Private Sub RemoveOptionValidation()
    On Error Resume Next
    ApiUiSheet().Range(CELL_SELECTED_OPTION).Validation.Delete
    On Error GoTo 0
End Sub

Private Sub ClearOptionTable()
    Dim ui As Worksheet
    Set ui = ApiUiSheet()

    ui.Range( _
        OPTION_DISPLAY_COLUMN & OPTION_FIRST_ROW & ":" & _
        OPTION_TOKEN_COLUMN & OPTION_LAST_ROW _
    ).ClearContents
End Sub

Private Sub ClearApiResultValues()
    WriteNamedValue "API_PartNumber", vbNullString
    WriteNamedValue "API_SKU", vbNullString
    WriteNamedValue "API_ConfigurationSignature", vbNullString
    WriteNamedValue "API_ConfiguredProductRegistryId", vbNullString
    WriteNamedValue "API_WasCreated", vbNullString
    WriteNamedValue "API_RequestCount", vbNullString
    WriteNamedValue "API_RuntimeRevision", vbNullString
    WriteNamedValue "API_StateToken", vbNullString
    WriteNamedValue "API_Status", "ready"
    WriteNamedValue "API_LastUpdatedUtc", Format$(Now, "yyyy-mm-dd\Thh:nn:ss")
End Sub

Private Sub WriteNamedValue(ByVal nameText As String, ByVal value As Variant)
    ThisWorkbook.Names(nameText).RefersToRange.Value = value
End Sub

Private Function ApiUiSheet() As Worksheet
    Set ApiUiSheet = ThisWorkbook.Worksheets(UI_SHEET)
End Function

Private Function NormalizeBaseUrl(ByVal value As String) As String
    value = Trim$(value)

    Do While Len(value) > 0 And Right$(value, 1) = "/"
        value = Left$(value, Len(value) - 1)
    Loop

    NormalizeBaseUrl = value
End Function

Private Function UrlEncode(ByVal value As String) As String
    Dim index As Long
    Dim character As String
    Dim code As Long
    Dim result As String

    For index = 1 To Len(value)
        character = Mid$(value, index, 1)
        code = AscW(character)

        If (code >= 48 And code <= 57) Or _
           (code >= 65 And code <= 90) Or _
           (code >= 97 And code <= 122) Or _
           character = "-" Or character = "_" Or _
           character = "." Or character = "~" Then
            result = result & character
        Else
            result = result & "%" & Right$("0" & Hex$(code And &HFF), 2)
        End If
    Next index

    UrlEncode = result
End Function

Private Sub ShowApiError( _
    ByVal operationName As String, _
    ByVal errorNumber As Long, _
    ByVal errorDescription As String _
)
    On Error Resume Next
    ApiUiSheet().Range(CELL_STATUS).Value = _
        operationName & " failed"
    On Error GoTo 0

    MsgBox _
        operationName & " failed." & vbCrLf & vbCrLf & _
        errorDescription & vbCrLf & vbCrLf & _
        "Error number: " & CStr(errorNumber), _
        vbCritical, _
        "Fybroc Pump Configurator"
End Sub

' ----------------------------------------------------------------------
' Minimal JSON parser supporting the API's objects, arrays, strings,
' numbers, booleans, and null values.
' ----------------------------------------------------------------------

Private Function JsonParseObject(ByVal jsonText As String) As Object
    mJsonText = jsonText
    mJsonPosition = 1

    JsonSkipWhitespace

    If JsonCurrentCharacter() <> "{" Then
        Err.Raise vbObjectError + 2100, , _
            "The API response is not a JSON object."
    End If

    Set JsonParseObject = JsonReadObject()

    JsonSkipWhitespace

    If mJsonPosition <= Len(mJsonText) Then
        Err.Raise vbObjectError + 2101, , _
            "Unexpected text after the JSON response."
    End If
End Function

Private Function JsonReadValue() As Variant
    JsonSkipWhitespace

    Select Case JsonCurrentCharacter()
        Case "{"
            Dim objectValue As Object
            Set objectValue = JsonReadObject()
            Set JsonReadValue = objectValue

        Case "["
            Dim arrayValue As Collection
            Set arrayValue = JsonReadArray()
            Set JsonReadValue = arrayValue

        Case """"
            JsonReadValue = JsonReadString()

        Case "t"
            JsonReadLiteral "true"
            JsonReadValue = True

        Case "f"
            JsonReadLiteral "false"
            JsonReadValue = False

        Case "n"
            JsonReadLiteral "null"
            JsonReadValue = Null

        Case "-", "0" To "9"
            JsonReadValue = JsonReadNumber()

        Case Else
            Err.Raise vbObjectError + 2102, , _
                "Unexpected JSON token at position " & CStr(mJsonPosition) & "."
    End Select
End Function

Private Function JsonReadObject() As Object
    Dim result As Object
    Set result = CreateObject("Scripting.Dictionary")
    result.CompareMode = vbBinaryCompare

    JsonExpectCharacter "{"
    JsonSkipWhitespace

    If JsonCurrentCharacter() = "}" Then
        mJsonPosition = mJsonPosition + 1
        Set JsonReadObject = result
        Exit Function
    End If

    Do
        JsonSkipWhitespace

        If JsonCurrentCharacter() <> """" Then
            Err.Raise vbObjectError + 2103, , _
                "A JSON object key must be a string."
        End If

        Dim key As String
        key = JsonReadString()

        JsonSkipWhitespace
        JsonExpectCharacter ":"

        If JsonValueIsObject() Then
            Dim objectItem As Object
            Set objectItem = JsonReadValue()
            result.Add key, objectItem
        Else
            Dim value As Variant
            value = JsonReadValue()
            result.Add key, value
        End If

        JsonSkipWhitespace

        Select Case JsonCurrentCharacter()
            Case "}"
                mJsonPosition = mJsonPosition + 1
                Exit Do

            Case ","
                mJsonPosition = mJsonPosition + 1

            Case Else
                Err.Raise vbObjectError + 2104, , _
                    "Expected ',' or '}' in JSON object."
        End Select
    Loop

    Set JsonReadObject = result
End Function

Private Function JsonReadArray() As Collection
    Dim result As New Collection

    JsonExpectCharacter "["
    JsonSkipWhitespace

    If JsonCurrentCharacter() = "]" Then
        mJsonPosition = mJsonPosition + 1
        Set JsonReadArray = result
        Exit Function
    End If

    Do
        If JsonValueIsObject() Then
            Dim objectItem As Object
            Set objectItem = JsonReadValue()
            result.Add objectItem
        Else
            Dim value As Variant
            value = JsonReadValue()
            result.Add value
        End If

        JsonSkipWhitespace

        Select Case JsonCurrentCharacter()
            Case "]"
                mJsonPosition = mJsonPosition + 1
                Exit Do

            Case ","
                mJsonPosition = mJsonPosition + 1

            Case Else
                Err.Raise vbObjectError + 2105, , _
                    "Expected ',' or ']' in JSON array."
        End Select
    Loop

    Set JsonReadArray = result
End Function

Private Function JsonValueIsObject() As Boolean
    JsonSkipWhitespace

    Dim character As String
    character = JsonCurrentCharacter()

    JsonValueIsObject = (character = "{" Or character = "[")
End Function

Private Function JsonReadString() As String
    JsonExpectCharacter """"

    Dim result As String
    Dim character As String

    Do While mJsonPosition <= Len(mJsonText)
        character = Mid$(mJsonText, mJsonPosition, 1)
        mJsonPosition = mJsonPosition + 1

        If character = """" Then
            JsonReadString = result
            Exit Function
        End If

        If character = "\" Then
            If mJsonPosition > Len(mJsonText) Then
                Err.Raise vbObjectError + 2106, , _
                    "Invalid JSON string escape."
            End If

            character = Mid$(mJsonText, mJsonPosition, 1)
            mJsonPosition = mJsonPosition + 1

            Select Case character
                Case """", "\", "/"
                    result = result & character
                Case "b"
                    result = result & Chr$(8)
                Case "f"
                    result = result & Chr$(12)
                Case "n"
                    result = result & vbLf
                Case "r"
                    result = result & vbCr
                Case "t"
                    result = result & vbTab
                Case "u"
                    If mJsonPosition + 3 > Len(mJsonText) Then
                        Err.Raise vbObjectError + 2107, , _
                            "Incomplete JSON Unicode escape."
                    End If

                    result = result & ChrW$(CLng("&H" & _
                        Mid$(mJsonText, mJsonPosition, 4)))
                    mJsonPosition = mJsonPosition + 4
                Case Else
                    Err.Raise vbObjectError + 2108, , _
                        "Unsupported JSON string escape."
            End Select
        Else
            result = result & character
        End If
    Loop

    Err.Raise vbObjectError + 2109, , _
        "Unterminated JSON string."
End Function

Private Function JsonReadNumber() As Variant
    Dim startPosition As Long
    startPosition = mJsonPosition

    Do While mJsonPosition <= Len(mJsonText)
        Dim character As String
        character = Mid$(mJsonText, mJsonPosition, 1)

        If InStr(1, "-+0123456789.eE", character, vbBinaryCompare) = 0 Then
            Exit Do
        End If

        mJsonPosition = mJsonPosition + 1
    Loop

    Dim token As String
    token = Mid$(mJsonText, startPosition, mJsonPosition - startPosition)

    If InStr(1, token, ".", vbBinaryCompare) > 0 Or _
       InStr(1, token, "e", vbTextCompare) > 0 Then
        JsonReadNumber = CDbl(Val(token))
    Else
        JsonReadNumber = CLng(Val(token))
    End If
End Function

Private Sub JsonReadLiteral(ByVal literalText As String)
    If Mid$(mJsonText, mJsonPosition, Len(literalText)) <> literalText Then
        Err.Raise vbObjectError + 2110, , _
            "Invalid JSON literal."
    End If

    mJsonPosition = mJsonPosition + Len(literalText)
End Sub

Private Sub JsonExpectCharacter(ByVal expectedCharacter As String)
    JsonSkipWhitespace

    If JsonCurrentCharacter() <> expectedCharacter Then
        Err.Raise vbObjectError + 2111, , _
            "Expected '" & expectedCharacter & _
            "' at JSON position " & CStr(mJsonPosition) & "."
    End If

    mJsonPosition = mJsonPosition + 1
End Sub

Private Sub JsonSkipWhitespace()
    Do While mJsonPosition <= Len(mJsonText)
        Select Case Mid$(mJsonText, mJsonPosition, 1)
            Case " ", vbTab, vbCr, vbLf
                mJsonPosition = mJsonPosition + 1
            Case Else
                Exit Do
        End Select
    Loop
End Sub

Private Function JsonCurrentCharacter() As String
    If mJsonPosition > Len(mJsonText) Then
        JsonCurrentCharacter = vbNullString
    Else
        JsonCurrentCharacter = Mid$(mJsonText, mJsonPosition, 1)
    End If
End Function

Private Function JsonEscape(ByVal value As String) As String
    value = Replace(value, "\", "\\")
    value = Replace(value, """", "\""")
    value = Replace(value, vbCr, "\r")
    value = Replace(value, vbLf, "\n")
    value = Replace(value, vbTab, "\t")
    JsonEscape = value
End Function

Private Function JsonObjectText( _
    ByVal jsonObject As Object, _
    ByVal key As String _
) As String
    If Not jsonObject.Exists(key) Then
        JsonObjectText = vbNullString
    ElseIf IsNull(jsonObject(key)) Or IsEmpty(jsonObject(key)) Then
        JsonObjectText = vbNullString
    Else
        JsonObjectText = CStr(jsonObject(key))
    End If
End Function

Private Function JsonObjectValue( _
    ByVal jsonObject As Object, _
    ByVal key As String _
) As Variant
    If Not jsonObject.Exists(key) Then
        JsonObjectValue = Empty
    Else
        JsonObjectValue = jsonObject(key)
    End If
End Function
