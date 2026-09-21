Attribute VB_Name = "Module1"
Option Explicit
Public dataSheetRanges As Variant
Public quoteRanges As Variant
Public motorOptRanges As Variant
Public baseOptRanges As Variant
Public headers As Variant
'Public configHeaders As Variant
'Public quoteHeaders As Variant
Public wksSheet1 As Worksheet
Public wksSheet2 As Worksheet
Public wksSheet3 As Worksheet
Public dbPath As String
Public lenHeaders As Integer
'Public lenConfHeaders As Integer
'Public lenQuoteHeaders As Integer
Public initialized As Boolean

Public Sub InitializeVariables()

    dataSheetRanges = Array("D6:F6", "D7:F7", "G7", "H7", "I7", "D8", "D9", "D10", "D11", "G8:I8", "G9:I9", "G10:I10", "G11:I11", "D14", "D15", "D16", "D17", "D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25", "D26", "D27", "D28", _
                            "D31", "D32", "D33", "D34", "D36", "D37", "D38", "D39", "D40", "D41", "D42", "D43", "D44", "D46", "D47", "D49", "D50", "D51", "D52", "D53", "D54", "D55", "D56", "D57", "D58", "D59", "D60", "D61", _
                            "D62", "D63", "D64", "D65", "D66", "G14", "H14", "G19", "H19", "G24:H24", "G25:H25", "G26:H26", "G27:H27", "G29:H30", "G31:H31", "G32:H32", "G33:H33", "G34:H34", "G35:H35", "G36:H36", "G37:H37", _
                            "G38:H38", "G39:H39", "G40:H40", "G41:H41", "G42:H42", "G43:H43", "G44:H44", "G45:H45", "G47:H47", "G48:H48", "G48:H49", "G50:H50", "G51:H51", "G52:H52", "G53:H53", "G54:H54", "G55:H55", "G57:H57", _
                            "G58:H58", "G59:H59", "G60:H60", "G61:H61", "G62:H62", "G63:H63", "G64:H64", "G65:H65", "G67:H67", "G68:H68", "G69:H69", "G70:H70")

    quoteRanges = Array("B7", "B3", "C5", "I5:J5", "F20:F23", "G20:G23", "H20:H23", "F24", "G24", "H24", "F25", "G25", "H25", "F26", "G26", "H26", "F27", "G27", "H27", "F28", "G28", "H28", "F29", _
                          "G29", "H29", "F30", "G30", "H30", "F31", "G31", "H31", "F32:F33", "G32:G33", "H32:H33", "F34", "G34", "H34", "F35", "G35", "H35", "F36", "G36", "H36", "F37", "G37", _
                          "H37", "F38", "G38", "H38", "F39", "G39", "H39", "F40", "G40", "H40", "F41", "G41", "H41", "F42", "G42", "H42", "F43", "G43", "H43", "F44", "G44", "H44", "F45", "G45", "H45", "F46", _
                          "G46", "H46", "F47", "G47", "H47", "F48", "G48", "H48", "F49", "B54")

    headers = Array("Pump Spec Number", "Part Number", "Revision", "Date Created", "By", "Pump Configuration", "Flow", "Fluid", "Fluid Temp (Nom/Max)", "NPSHA", "TDH", "Specific Gravity", "Viscosity", "Series", "Pump Size", "Pump Material", "Casing Material", "Casing Drain", "Casing Taps", "Casing Gasket", "Flange Configuration", "Spot Facing", "Casing Wear Rings", "Tack weld Wear Rings", "Casing Mounting", "Seal Chamber Config", "Shipping Gasket", "Casing Heat Jacket", "Impeller Trim", "Impeller Balance", "Impeller Material", "Imp Wear Rings Material", _
                    "Shaft Configuration", "Shaft Material", "Lubrication Options", "Oil Seal", "Oiler Options", "Sight Glass", "Bearing Frame Cooling", "Magnetic Drain", "Expansion Chamber", "Coupling Type", "Coupling Guard", "Seal Option", "Seal Mfr", "Seal Configuration", "Seal Type", "Gland Type", "Gland Gasket", "Shaft Sleeve Material", "Inboard Rotating Face Material", "Inboard Stationary Face Material", "Inboard Seal Elastomers", "Outboard Rotating Face Material", "Outboard Stationary Face Material", "Outboard Seal Elastomers", "Hydropads", "Pumping Ring", "Throttle Bushing", _
                    "Min Flo Bushing", "Lantern Ring", "Flush Plan", "Flush Plan Code", "Barrier Plan", "Barrier Plan Code", "Barrier Plan Extras", "Cooling Plan", "Cooling Plan Piping", "Cooling Plan Extras", "Motor Options", "Motor Control", "Power HP", "Speed", "Voltage", "Phase/Hertz", "Frame", "Enclosure", "Efficiency", "C Face Adapter Option", "Manufacturer", "Custom Option 1", "Custom Option 2", "Custom Option 3", "Drip Cover", "Conduit box", "Baseplate Type", "Drip Pan", "Alignment lugs", "Lifting lugs", "Levelling Screws", "Grounding Lug", "Grout Hole", "Isolation Pads", _
                    "Stilts", "Performance Testing", "Hydro Test", "Vibration", "Sound Level", "General Inspection", "Documentation 1", "Documentation 2", "Documentation 3", "Documentation 4", "Paint", "Coating", "Auxillary Nameplate", "Crating", "Customer Name", "Distributor", "Quote Number", "Project Name", "Qty Line 1", "List Line 1", "Discount Line 1", "Qty Line 2", "List Line 2", "Discount Line 2", "Qty Line 3", "List Line 3", "Discount Line 3", "Qty Line 4", "List Line 4", "Discount Line 4", "Qty Line 5", "List Line 5", "Discount Line 5", "Qty Line 6", "List Line 6", _
                    "Discount Line 6", "Qty Line 7", "List Line 7", "Discount Line 7", "Qty Line 8", "List Line 8", "Discount Line 8", "Qty Line 9", "List Line 9", "Discount Line 9", "Qty Line 10", "List Line 10", "Discount Line 10", "Qty Line 11", "List Line 11", "Discount Line 11", "Qty Line 12", "List Line 12", "Discount Line 12", "Qty Line 13", "List Line 13", "Discount Line 13", "Qty Line 14", "List Line 14", "Discount Line 14", "Qty Line 15", "List Line 15", "Discount Line 15", "Qty Line 16", "List Line 16", "Discount Line 16", "Qty Line 17", "List Line 17", "Discount Line 17", _
                    "Qty Line 18", "List Line 18", "Discount Line 18", "Qty Line 19", "List Line 19", "Discount Line 19", "Qty Line 20", "List Line 20", "Discount Line 20", "Qty Line 21", "List Line 21", "Discount Line 21", "Qty Line 22", "List Line 22", "Discount Line 22", "Qty Line 23", "List Line 23", "Discount Line 23", "Qty Line 24", "List Line 24", "Discount Line 24", "Qty Line 25", "List Line 25", "Discount Line 25", "Qty Line 26", "AE Name", "AE Alias", "System Time")

'    configHeaders = Array("Pump Spec Number", "Part Number", "Revision", "Date Created", "By", "Pump Configuration", "Flow", "Fluid", "Fluid Temp (Nom/Max)", "NPSHA", "TDH", "Specific Gravity", "Viscosity", "Series", "Pump Size", "Pump Material", "Casing Material", "Casing Drain", "Casing Taps", "Casing Gasket", "Flange Configuration", "Spot Facing", "Casing Wear Rings", "Tack weld Wear Rings", "Casing Mounting", "Seal Chamber Config", "Shipping Gasket", "Casing Heat Jacket", "Impeller Trim", "Impeller Balance", "Impeller Material", "Imp Wear Rings Material", _
'                    "Shaft Configuration", "Shaft Material", "Lubrication Options", "Oil Seal", "Oiler Options", "Sight Glass", "Bearing Frame Cooling", "Magnetic Drain", "Expansion Chamber", "Coupling Type", "Coupling Guard", "Seal Option", "Seal Mfr", "Seal Configuration", "Seal Type", "Gland Type", "Gland Gasket", "Shaft Sleeve Material", "Inboard Rotating Face Material", "Inboard Stationary Face Material", "Inboard Seal Elastomers", "Outboard Rotating Face Material", "Outboard Stationary Face Material", "Outboard Seal Elastomers", "Hydropads", "Pumping Ring", "Throttle Bushing", _
'                    "Min Flo Bushing", "Lantern Ring", "Flush Plan", "Flush Plan Code", "Barrier Plan", "Barrier Plan Code", "Barrier Plan Extras", "Cooling Plan", "Cooling Plan Piping", "Cooling Plan Extras", "Motor Options", "Motor Control", "Power HP", "Speed", "Voltage", "Phase/Hertz", "Frame", "Enclosure", "Efficiency", "C Face Adapter Option", "Manufacturer", "Custom Option 1", "Custom Option 2", "Custom Option 3", "Drip Cover", "Conduit box", "Baseplate Type", "Drip Pan", "Alignment lugs", "Lifting lugs", "Levelling Screws", "Grounding Lug", "Grout Hole", "Isolation Pads", _
'                    "Stilts", "Performance Testing", "Hydro Test", "Vibration", "Sound Level", "General Inspection", "Documentation 1", "Documentation 2", "Documentation 3", "Documentation 4", "Paint", "Coating", "Auxillary Nameplate", "Crating", "AE Alias", "System Time")
'
'    quoteHeaders = Array("Customer Name", "Distributor", "Quote Number", "Project Name", "Qty Line 1", "List Line 1", "Discount Line 1", "Qty Line 2", "List Line 2", "Discount Line 2", "Qty Line 3", "List Line 3", "Discount Line 3", "Qty Line 4", "List Line 4", "Discount Line 4", "Qty Line 5", "List Line 5", "Discount Line 5", "Qty Line 6", "List Line 6", "Discount Line 6", "Qty Line 7", "List Line 7", "Discount Line 7", "Qty Line 8", "List Line 8", "Discount Line 8", _
'                    "Qty Line 9", "List Line 9", "Discount Line 9", "Qty Line 10", "List Line 10", "Discount Line 10", "Qty Line 11", "List Line 11", "Discount Line 11", "Qty Line 12", "List Line 12", "Discount Line 12", "Qty Line 13", "List Line 13", "Discount Line 13", "Qty Line 14", "List Line 14", "Discount Line 14", "Qty Line 15", "List Line 15", "Discount Line 15", "Qty Line 16", "List Line 16", "Discount Line 16", "Qty Line 17", "List Line 17", "Discount Line 17", "Qty Line 18", "List Line 18", "Discount Line 18", "Qty Line 19", "List Line 19", "Discount Line 19", "Qty Line 20", "List Line 20", _
'                    "Discount Line 20", "Qty Line 21", "List Line 21", "Discount Line 21", "Qty Line 22", "List Line 22", "Discount Line 22", "Qty Line 23", "List Line 23", "Discount Line 23", "Qty Line 24", "List Line 24", "Discount Line 24", "Qty Line 25", "List Line 25", "Discount Line 25", "Qty Line 26", "AE Name", "AE Alias", "System Time")
                    
    motorOptRanges = Array("G31:H31", "G32:H32", "G33:H33", "G34:H34", "G35:H35", "G36:H36", "G37:H37", "G38:H38", "G39:H39", "G40:H40", "G41:H41", "G42:H42", "G43:H43", "G44:H44", "G45:H45")
    baseOptRanges = Array("G48:H48", "G49:H49", "G50:H50", "G51:H51", "G52:H52", "G53:H53", "G54:H54", "G55:H55")

    Set wksSheet1 = ThisWorkbook.Sheets("Data Sheet")
    Set wksSheet2 = ThisWorkbook.Sheets("Formal Quote")
    Set wksSheet3 = ThisWorkbook.Sheets("Formal Quote (OEM)")
    
    dbPath = "P:\Dean\DEAN_PROJECTS\Numbering Project\Quote Database_TEST.accdb"
    lenHeaders = UBound(headers)
'    lenConfHeaders = UBound(configHeaders)
'    lenQuoteHeaders = UBound(quoteHeaders)
    initialized = True
    Application.EnableEvents = True
    Application.Calculation = xlCalculationAutomatic
End Sub

Public Function SearchDatabase(searchSheet As String, searchFields As Variant, searchValues As Variant, exactMatch As Boolean) As Variant
    Dim conn As Object
    Dim cmd As Object
    Dim rs As Object
    Dim sql As String
    Dim results() As Variant
    Dim i As Integer
    Dim numFields As Integer
    If Not initialized Then
        Call InitializeVariables
    End If

    numFields = UBound(searchFields)

    ' Define and open the connection string for an Access file (using ACE OLEDB 12.0 provider)
    On Error GoTo errHandler
    Set conn = CreateObject("ADODB.Connection")
    conn.Open "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=" & dbPath & ";Persist Security Info=False;"

Search:

    ' Build SQL
    
    If exactMatch Then
        sql = "SELECT * FROM [" & searchSheet & "] WHERE "
        For i = 0 To numFields
            sql = sql & "[" & searchFields(i) & "] = ? AND "
        Next i
    Else
        sql = "SELECT * FROM [" & searchSheet & "] WHERE "
        For i = 0 To numFields
            sql = sql & "[" & searchFields(i) & "] LIKE ? AND "
        Next i
    End If
    
    ' Trim sql text
    sql = Left(sql, Len(sql) - 5)
'    Debug.Print sql

    ' Prepare command
    Set cmd = CreateObject("ADODB.Command")
    Set cmd.ActiveConnection = conn
    cmd.CommandText = sql
'    cmd.CommandType = adCmdText

    ' Add parameters from array
    If exactMatch Then
        For i = 0 To numFields
            cmd.Parameters.Append cmd.CreateParameter("p" & i, 200, 1, 255, CStr(searchValues(i)))
        Next i
    Else
        For i = 0 To numFields
            cmd.Parameters.Append cmd.CreateParameter("p" & i, 200, 1, 255, "%" & CStr(searchValues(i)) & "%")
        Next i
    End If

    Set rs = CreateObject("ADODB.recordset")
    
    ' Execute insert
    Debug.Print cmd.CommandText
    On Error GoTo errHandler
    Set rs = cmd.Execute
    
'    ' The sheet name in SQL must be followed by a dollar sign ($) and enclosed in brackets []
'    If exactMatch Then
'        sql = "SELECT * FROM [" & searchSheet & "] WHERE [" & searchFields(0) & "] = " & searchValues(0)
'        For i = 1 To UBound(searchFields)
'            sql = sql & " AND [" & searchFields(i) & "] = " & searchValues(i)
'        Next
'    Else
'        sql = "SELECT * FROM [" & searchSheet & "] WHERE [" & searchFields(0) & "] LIKE '%" & searchValues(0) & "%'"
'        For i = 1 To UBound(searchFields)
'            sql = sql & " AND [" & searchFields(i) & "] LIKE '%" & searchValues(i) & "%'"
'        Next
'    End If
'    Debug.Print sql
'
'    ' Open the recordset with the results of the query
'    Set rs = CreateObject("ADODB.recordset")
'    rs.Open sql, Conn, adOpenStatic, adLockReadOnly
'    ' Check if a row was found

    If Not rs.EOF Then
        ' Process the retrieved row (e.g., display a value, copy to current sheet)
        results = rs.GetRows()

        Dim r As Integer, j As Integer
        Dim temp As Variant
        For r = 0 To UBound(results, 1)
            i = LBound(results, 2)
            j = UBound(results, 2)
            Do While i < j
                temp = results(r, i)
                results(r, i) = results(r, j)
                results(r, j) = temp
                i = i + 1
                j = j - 1
            Loop
        Next
    Else
        ReDim results(0, 0)
        results(0, 0) = -1
    End If

    SearchDatabase = results

CleanExit:
    If conn.State = 1 Then conn.Close: Set conn = Nothing
    If rs.State = 1 Then rs.Close: Set rs = Nothing
    'Application.EnableEvents = True
    Exit Function

errHandler:
    MsgBox err.Number & ": " & err.Description
    GoTo CleanExit

End Function

Sub getSealOptions()

    Dim searchFields As Variant
    Dim searchValues() As Variant
    Dim conn As Object
    Dim rs As Object
    Dim sql As String
    Dim results() As Variant
    Dim i As Integer
    If Not initialized Then
        Call InitializeVariables
    End If

    ' Define and open the connection string for an Access file (using ACE OLEDB 12.0 provider)
    On Error GoTo errHandler
    Set conn = CreateObject("ADODB.Connection")
    conn.Open "Provider=Microsoft.ACE.OLEDB.12.0;Data Source=" & "C:\Users\jdadams\OneDrive - Tusk Industrial LLC\Documents\Seal Numbering.accdb" & ";Persist Security Info=False;"

    searchFields = Array("Seal Type", "Seal Manufacturer", "Inboard Rotating Face", "Inboard Stationary Face", "Inboard Elastomers", "Outboard Rotating Face", "Outboard Stationary Face", "Outboard Elastomers", "Hydropads", "Pumping Ring", "Throttle Bushing", "Min Flo Bushing", "Lantern Ring", "Inboard Seal Hardware", "Outboard Seal Hardware", "Seal Chamber Config", "Gland Style", "Gland Gasket", "Sleeve Material")
    searchValues = Array("", wksSheet1.Range("G15").Value, wksSheet1.Range("G21").Value, wksSheet1.Range("G22").Value, wksSheet1.Range("G23").Value, wksSheet1.Range("G24").Value, wksSheet1.Range("G25").Value, wksSheet1.Range("G26").Value, "", wksSheet1.Range("G27").Value, wksSheet1.Range("G28").Value, wksSheet1.Range("G29").Value, wksSheet1.Range("G31").Value, "", "", "Standard", wksSheet1.Range("G18").Value, wksSheet1.Range("G19").Value, wksSheet1.Range("G20").Value)

Search:
    
    ' The sheet name in SQL must be followed by a dollar sign ($) and enclosed in brackets []
    Dim searchVal As String
    sql = "SELECT * FROM [Combined Table] WHERE [" & searchFields(0) & "] LIKE '%" & searchValues(0) & "%'"
        For i = 1 To UBound(searchFields)
            If IsEmpty(searchValues(i)) Then searchVal = "" Else searchVal = searchValues(i)
            sql = sql & " AND [" & searchFields(i) & "] LIKE '%" & searchVal & "%'"
        Next
    ' Open the recordset with the results of the query
    Debug.Print sql
    Set rs = CreateObject("ADODB.recordset")
    rs.Open sql, conn, adOpenStatic, adLockReadOnly
    ' Check if a row was found
    If Not rs.EOF Then
        ' Process the retrieved row (e.g., display a value, copy to current sheet)
        results = rs.GetRows()

        Dim r As Integer, j As Integer
        Dim temp As Variant
        For r = 0 To UBound(results, 1)
            i = LBound(results, 2)
            j = UBound(results, 2)
            Do While i < j
                temp = results(r, i)
                results(r, i) = results(r, j)
                results(r, j) = temp
                i = i + 1
                j = j - 1
            Loop
        Next
    Else
        ReDim results(0, 0)
        results(0, 0) = -1
    End If

CleanExit:
    If conn.State = 1 Then conn.Close: Set conn = Nothing
    If rs.State = 1 Then rs.Close: Set rs = Nothing
    'Application.EnableEvents = True
    Exit Sub

errHandler:
    MsgBox err.Number & ": " & err.Description
    GoTo CleanExit

End Sub

Public Function writeToDataBase(dataFields As Variant, dataValues As Variant)
    
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False

    Dim conn As Object, cmd As Object
    Dim rs As Object
    Dim sql As String
    Dim colNames As String
    Dim paramMarks As String
    Dim numFields As Integer
    Dim i As Integer
    
    numFields = UBound(dataFields)
'    ReDim Preserve dataValues(0 To numFields)
'    ReDim Preserve dataFields(0 To numFields)
    
    ' Build column list and parameter placeholders
    For i = 0 To numFields
        colNames = colNames & "[" & dataFields(i) & "], "
        paramMarks = paramMarks & "?, "
    Next i
    
    ' Trim trailing commas
    colNames = Left(colNames, Len(colNames) - 2)
    paramMarks = Left(paramMarks, Len(paramMarks) - 2)

    ' Build SQL
    sql = "INSERT INTO [Custom Confs] (" & colNames & ") VALUES (" & paramMarks & ");"
'    Debug.Print sql

    ' Prepare command
    Set conn = CreateObject("ADODB.Connection")
    conn.Open "Provider=Microsoft.ACE.OLEDB.12.0;" & _
              "Data Source=" & dbPath & ";"
    Set cmd = CreateObject("ADODB.Command")
    Set cmd.ActiveConnection = conn
    cmd.CommandText = sql

    ' Add parameters from array
    For i = 0 To numFields
        cmd.Parameters.Append cmd.CreateParameter("p" & i, 200, 1, 255, CStr(dataValues(i)))
    Next i

    ' Execute insert
'    Debug.Print cmd.commandText
    On Error GoTo errHandler
    cmd.Execute
    MsgBox "The data was succuessfully written to the database.", vbInformation
CleanExit:
    If Not (conn Is Nothing) Then conn.Close: Set conn = Nothing
    Application.EnableEvents = True
    Exit Function

errHandler:
    MsgBox err.Number & ": " & err.Description
    GoTo CleanExit
End Function

Public Function getPartialArray(fullArr As Variant, startPos As Integer, endPos As Integer) As Variant

    Dim partArr() As Variant
    Dim ctr As Integer
    Dim i As Variant
    
    ReDim partArr(endPos - startPos - 1)
    
    ctr = 0
    For i = 0 To UBound(fullArr)
        If i > startPos And i <= endPos Then
            partArr(ctr) = fullArr(i)
            ctr = ctr + 1
        End If
    Next i
    
    getPartialArray = partArr
    
End Function
