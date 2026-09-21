Attribute VB_Name = "Sheet1"
Attribute VB_Base = "0{00020820-0000-0000-C000-000000000046}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = True
Attribute VB_Control = "SearchDatabase, 24, 1, MSForms, CommandButton"
Attribute VB_Control = "RestoreFromDatabase, 25, 2, MSForms, CommandButton"
Attribute VB_Control = "ClearSearchResults, 26, 3, MSForms, CommandButton"
Attribute VB_Control = "ClearDataSheet, 27, 4, MSForms, CommandButton"
Attribute VB_Control = "SetDefaultOptions, 29, 5, MSForms, CommandButton"
Attribute VB_Control = "SavePumpConfiguration, 32, 6, MSForms, CommandButton"
Private Sub ClearDataSheet_Click()
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual
    
    Dim targetRange() As Variant
    ReDim targetRange(UBound(dataSheetRanges) - 1)
    
    ctr = 0
    For Each rng In dataSheetRanges
        If ctr > 0 Then targetRange(ctr - 1) = rng
        ctr = ctr + 1
    Next rng
    
    clearRange (targetRange)
    Application.EnableEvents = True
    Application.Calculation = xlCalculationAutomatic
End Sub

Private Sub ClearSearchResults_Click()
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False
    
    wksSheet1.Range("P7:Y26").ClearContents
    Application.EnableEvents = True
End Sub

Private Sub SavePumpConfiguration_Click()
'    MsgBox "This feature has not been implemented yet." & vbCrLf & "Use save button of Formal Quote tab instead.", vbInformation
    Dim numFields As Integer
    Dim SheetName As String
    Dim vals() As Variant
    Dim results() As Variant
    Dim userInput As String
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False

    ' Search for existing configuration first
    numFields = UBound(headers)
    ReDim vals(numFields)
    SheetName = "Custom Confs"
    
    ctr = 0
    For i = 0 To UBound(dataSheetRanges)
'        fields(ctr) = headers(ctr)
        modifiedRange = dataSheetRanges(i)
        If Len(modifiedRange) > 3 Then
            modifiedRange = Left(modifiedRange, (Len(modifiedRange) - 1) / 2)
        End If
        If Not (IsEmpty(wksSheet1.Range(modifiedRange))) Then
            vals(ctr) = wksSheet1.Range(modifiedRange).Value
        Else
            vals(ctr) = ""
        End If
        ctr = ctr + 1
    Next i

    For i = 0 To UBound(quoteRanges)
'        fields(ctr) = headers(ctr)
        modifiedRange = quoteRanges(i)
        If Len(modifiedRange) > 3 Then
            modifiedRange = Left(modifiedRange, (Len(modifiedRange) - 1) / 2)
        End If
        If Not (IsEmpty(wksSheet2.Range(modifiedRange))) Then
            vals(ctr) = wksSheet2.Range(modifiedRange).Value
        Else
            vals(ctr) = ""
        End If
        ctr = ctr + 1
    Next i
    
    vals(numFields - 1) = Environ("USERNAME")
    vals(numFields) = Now

'    For i = 0 To UBound(dataSheetRanges)
'        fields(i) = headers(i)
'        tempRange = dataSheetRanges(i)
'        If Len(tempRange) > 3 Then
'            tempRange = Left(tempRange, (Len(tempRange) - 1) / 2)
'        End If
'        If Not (IsEmpty(wksSheet1.Range(tempRange))) Then
'            vals(i) = wksSheet1.Range(tempRange).Value
'        Else
'            vals(i) = ""
'        End If
'    Next

    pumpFields = getPartialArray(headers, 12, UBound(dataSheetRanges))
    pumpVals = getPartialArray(vals, 12, UBound(dataSheetRanges))

    results = Module1.SearchDatabase(SheetName, pumpFields, pumpVals, True)
    If Not results(0, 0) = -1 Then
        ' If matching configuration is found, recover it's accompanying part number
        wksSheet1.Range("D7").Value = results(2, 0)
        MsgBox "The existing part number was restored.", vbInformation, "Matching configuration found!"
    Else
        results = Module1.SearchDatabase(SheetName, Array(pumpFields(0), pumpFields(1)), Array(pumpVals(0), pumpVals(1)), True)
        If Not results(0, 0) = -1 Then
            numConfs = UBound(results, 2) + 1
            newNum = Left(wksSheet1.Range("D6").Value, 4) & "_" & Format(numConfs + 1, "000000")
            wksSheet1.Range("D7").Value = newNum
            vals(1) = newNum
        Else
            wksSheet1.Range("D7").Value = Left(wksSheet1.Range("D6").Value, 4) & "_000000"
        End If
'        MsgBox "A part number was created and added to database successfully.", vbInformation, "New configuration detected!"
    End If
    writeToDataBase headers, vals
    
End Sub

Private Sub RestoreFromDatabase_Click()
    Dim SheetName As String
    Dim searchFields() As Variant
    Dim searchVals() As Variant
    Dim results() As Variant
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual
                    
    ' Define the path to your external Access file
    SheetName = "Custom Confs"
    searchFields = Array("ID")
        
Search:
    searchVals = Array(ActiveCell.Value)
    
    results = Module1.SearchDatabase(SheetName, searchFields, searchVals, True)
    ctr = 0
    numc_1 = UBound(dataSheetRanges) + 1
    numc_2 = UBound(dataSheetRanges) + UBound(quoteRanges) + 1
    For c = 2 To numc_1
        wksSheet1.Range(dataSheetRanges(ctr + 1)).Value = results(c, 0)
        ctr = ctr + 1
    Next

    ctr = 0
    For c = numc_1 + 1 To numc_2 + 1
        wksSheet2.Range(quoteRanges(ctr)).Value = results(c, 0)
        ctr = ctr + 1
    Next
    MsgBox "The configuration was succesfully restored.", vbInformation
    
Done:
    Application.EnableEvents = True
    Application.Calculation = xlCalculationAutomatic
    Exit Sub

errHandler:
    MsgBox err.Number & ": " & err.Description
    GoTo Done
    
End Sub

Private Sub SearchDatabase_Click()
    Dim SheetName As String
    Dim searchFields() As Variant
    Dim searchVals() As Variant
    Dim results() As Variant
    Dim userInput As String
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False
    
' Define the path to your external Access file
    SheetName = "Custom Confs"
Search:
    searchType = InputBox(Prompt:="Enter 0 to search by Quote Number" & vbNewLine & _
                                  "Enter 1 to search by Date" & vbNewLine & _
                                  "Enter 2 to search by Project Name" & vbNewLine & _
                                  "Enter 3 to search by Customer" & vbNewLine & _
                                  "Enter 4 to search by A.E. Name" & vbNewLine & _
                                  "Enter 5 to search by Pump Series and Size", Title:="How would you like to search the database?")
    Select Case searchType
    
    Case "0"
        searchFields = Array("Quote Number")
        userInput = InputBox(Prompt:="Returns an exact match. Entry must be the entire quote number.", Title:="Search Database by Quote Number", Default:="Enter Quote Number Here")
        If StrPtr(userInput) = 0 Then MsgBox "Search canceled", vbExclamation: GoTo Done Else searchVals = Array(userInput)
        results = Module1.SearchDatabase(SheetName, searchFields, searchVals, True)
    Case "1"
        searchFields = Array("System Time")
        userInput = InputBox(Prompt:="Entry can be a partial date. Enter nothing to return all records.", Title:="Search Database by Date", Default:="Enter Date of Creation Here")
        If StrPtr(userInput) = 0 Then MsgBox "Search canceled", vbExclamation: GoTo Done Else searchVals = Array(userInput)
        results = Module1.SearchDatabase(SheetName, searchFields, searchVals, False)
    Case "2"
        searchFields = Array("Project Name")
        userInput = InputBox(Prompt:="Entry can be a partial project name. Enter nothing to return all records.", Title:="Search Database by Project name", Default:="Enter Project Name Here")
        If StrPtr(userInput) = 0 Then MsgBox "Search canceled", vbExclamation: GoTo Done Else searchVals = Array(userInput)
        results = Module1.SearchDatabase(SheetName, searchFields, searchVals, False)
    Case "3"
        searchFields = Array("Distributor")
Case3:
        userInput = InputBox(Prompt:="Returns all records that contain the entered value in Distributor name.", Title:="Search Database by Distributor name", Default:="Enter Distributor Name Here")
        If StrPtr(userInput) = 0 Then
            MsgBox "Search canceled", vbExclamation
            GoTo Done
        ElseIf userInput = "" Then
            MsgBox "You must enter a customer name.", vbExclamation
            GoTo Case3
        Else
            searchVals = Array(userInput)
            results = Module1.SearchDatabase(SheetName, searchFields, searchVals, False)
        End If
    Case "4"
        searchFields = Array("AE Name")
        userInput = InputBox(Prompt:="Returns all records created by entered A.E. name. Partial names are allowed.", Title:="Search Database by Distributor name", Default:="Enter A.E. Name Here")
        If StrPtr(userInput) = 0 Then MsgBox "Search canceled", vbExclamation: GoTo Done Else searchVals = Array(userInput)
        results = Module1.SearchDatabase(SheetName, searchFields, searchVals, False)
    Case "5"
        pumpSeries = InputBox("Partial entry is allowed. Enter nothing to return all series.", "Enter the series of pump you would like to search for", "Example: R4140")
        If StrPtr(pumpSeries) = 0 Then MsgBox "Search canceled", vbExclamation: GoTo Done
        pumpSize = InputBox("Entry must be formatted as _x_x_. Partial entry is allowed. Enter nothing to return all sizes.", "Enter the size of pump you would like to search for.", "Example: 3x4x8.5")
        If StrPtr(pumpSize) = 0 Then MsgBox "Search canceled", vbExclamation: GoTo Done
        searchFields = Array("Series", "Pump Size")
        searchVals = Array(pumpSeries, pumpSize)
        results = Module1.SearchDatabase(SheetName, searchFields, searchVals, False)
    Case ""
        MsgBox "Search canceled.", vbInformation
        Exit Sub
    Case Else
        MsgBox "Please try again.", vbExclamation, "Unknown command entered!"
        GoTo Search
    End Select
    
    If Not results(0, 0) = -1 Then
        ' Process the retrieved row (e.g., display a value, copy to current sheet)
        num_r = UBound(results, 2) + 1

'        results = reverseResults(results)
        i = 7
        j = 16
        ctr = 0
ReturnData:
        wksSheet1.Range("P7:Y26").ClearContents
        num_returned = Application.WorksheetFunction.Min(num_r - 20 * ctr, 20)
        For r = 0 To num_returned - 1
            wksSheet1.Cells(i + r, j).Value = "'" & results(0, 20 * ctr + r)
            wksSheet1.Cells(i + r, j + 1).Value = "'" & results(2, 20 * ctr + r)
            wksSheet1.Cells(i + r, j + 2).Value = "'" & results(14, 20 * ctr + r)
            wksSheet1.Cells(i + r, j + 3).Value = "'" & results(15, 20 * ctr + r)
            wksSheet1.Cells(i + r, j + 4).Value = "'" & results(6, 20 * ctr + r)
            wksSheet1.Cells(i + r, j + 5).Value = "'" & results(109, 20 * ctr + r)
            wksSheet1.Cells(i + r, j + 6).Value = "'" & results(110, 20 * ctr + r)
            wksSheet1.Cells(i + r, j + 7).Value = "'" & results(111, 20 * ctr + r)
            wksSheet1.Cells(i + r, j + 8).Value = "'" & results(188, 20 * ctr + r)
            recordDate = results(190, 20 * ctr + r)
            If Not recordDate = "" Then
                wksSheet1.Cells(i + r, j + 9).Value = "'" & Left(recordDate, InStr(1, recordDate, " ") - 1)
            Else
                wksSheet1.Cells(i + r, j + 9).Value = ""
            End If
        Next
        
        If num_returned >= 20 And ctr = 0 Then
            num_remaining = Application.WorksheetFunction.Min(num_r - 20 * (ctr + 1), 20)
            response = MsgBox("Currently displaying the 20 most recent entries." & vbCrLf & vbCrLf & _
                              "Would you like to return the next " & num_remaining & " records?", vbYesNo, "The search found " & num_r & " matching records!")
            If response = vbYes Then
                ctr = ctr + 1
                GoTo ReturnData
            End If
        ElseIf num_returned >= 20 Then
            num_remaining = Application.WorksheetFunction.Min(num_r - 20 * (ctr + 1), 20)
                response = MsgBox("Currently displaying the next 20 entries." & vbCrLf & vbCrLf & _
                                  "Would you like to return the next " & num_remaining & " records?", vbYesNo, "The search found " & num_r & " matching records!")
                If response = vbYes Then
                    ctr = ctr + 1
                    GoTo ReturnData
                End If
        ElseIf ctr = 0 Then
            MsgBox "Found " & num_r & " matching records.", vbInformation
        Else
            MsgBox "Returned the final " & num_remaining & " records.", vbInformation
        End If
        wksSheet1.Range("P7").Select
    Else
        'Debug.Print "No matching record found in the database"
        response = MsgBox("Would you like to try a different search?", vbYesNo, "Could not find a record of that in the database!")
            If response = vbYes Then
                GoTo Search
            End If
    End If
    
Done:
    Application.EnableEvents = True
    Exit Sub

errHandler:
    MsgBox err.Number & ": " & err.Description
    GoTo Done
End Sub

Private Sub SetDefaultOptions_Click()
    Dim SheetName As String
    Dim searchFields() As Variant
    Dim searchVals() As Variant
    Dim results() As Variant
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual
    SheetName = "Standard Confs"

    On Error GoTo errHandler
    pumpSeries = wksSheet1.Range("D14").Value
    pumpSize = wksSheet1.Range("D15").Value
    searchFields = Array("Series", "Pump Size")
    searchVals = Array(pumpSeries, pumpSize)
    results = Module1.SearchDatabase(SheetName, searchFields, searchVals, True)

    If Not results(0, 0) = -1 Then
        ctr = 0
        numc_1 = UBound(dataSheetRanges) + 1
        numc_2 = UBound(dataSheetRanges) + UBound(quoteRanges) + 1
        For c = 2 To numc_1
            wksSheet1.Range(dataSheetRanges(ctr + 1)).Value = results(c, 0)
            ctr = ctr + 1
        Next

        ctr = 0
        For c = numc_1 + 1 To numc_2 + 1
            wksSheet2.Range(quoteRanges(ctr)).Value = results(c, 0)
            ctr = ctr + 1
        Next
        MsgBox "The configuration was succesfully restored.", vbInformation
    Else
        MsgBox "The configuration failed to be restored. Please ensure that you have selected a valid Series/Size combination", vbExclamation
    End If
    
Done:
    Application.EnableEvents = True
    Application.Calculation = xlCalculationAutomatic
    Exit Sub

errHandler:
    MsgBox err.Number & ": " & err.Description
    GoTo Done

End Sub

Private Sub Worksheet_Change(ByVal Target As Range)
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False

    ThisWorkbook.Connections("Query - User Selections").Refresh
'    ThisWorkbook.Connections("Query - Seal Options").Refresh
    
    If Target.Cells.Count < 2 Then
        'Baseplate selection
        If Target.Row = 38 And Target.Column = 4 Then
            If Target.Value = "NONE" Then
                setRangeNA (baseOptRanges)
                GoTo exitSub
            End If
        End If
        
        ' Motor selection
        If Target.Row = 46 And Target.Column = 7 Then
            If Target.Value = "No Motor" Then
                setRangeNA (motorOptRanges)
                GoTo exitSub
            End If
        End If
        
        If Target.Row >= 62 And Target.Row <= 65 And Target.Column = 7 Then
            myInput = Target.Value
            If InStr(myInput, "MTR") > 0 Then
                Dim form As New MTR_Selection
                form.Show vbModal
                
                If form.Cancelled = True Then
                    wksSheet1.Range("G" & Target.Row & ":H" & Target.Row).ClearContents
                    MsgBox "The operation was cancelled"
                Else
                    Target.Value = "MTR " & form.Selections()
                End If
                Unload form
                Set form = Nothing
            End If
            GoTo exitSub
        End If
        
        If Target.Row = 8 And Target.Column = 4 Then
            myInput = Target.Value
            Select Case myInput
                Case "Pump Only"
                    GoTo SetPO:
                Case "Pump and Baseplate"
                    GoTo SetPB
                Case "Pump, Baseplate, and Coupling"
                    GoTo SetPBC
                Case "Pump and Motor"
                    GoTo SetPM
                Case "Pump, Baseplate, and Motor"
                    GoTo SetPBM
                Case "Pump, Baseplate, Coupling and Motor"
                    GoTo SetPBCM
                Case "Pump and Coupling"
                    GoTo SetPC
                Case Else
                    MsgBox "ERROR: Unknown command", vbExclamation
                    GoTo exitSub
            End Select
SetPO:
            wksSheet1.Range("D38").Value = "NONE"
            setRangeNA (baseOptRanges)
            wksSheet1.Range("D49").Value = "NONE"
            wksSheet1.Range("G47:H47").Value = "Supplied by others; Installed by others"
            clearRange (motorOptRanges)
            GoTo exitSub
SetPB:
            wksSheet1.Range("D49").Value = "NONE"
            wksSheet1.Range("G47:H47").Value = "Supplied by others; Installed by others"
            clearRange (motorOptRanges)
            GoTo exitSub
SetPBC:
            wksSheet1.Range("G47:H47").Value = "Supplied by others; Installed by others"
            clearRange (motorOptRanges)
            GoTo exitSub
SetPM:
            wksSheet1.Range("D38").Value = "NONE"
            clearRange (baseOptRanges)
            wksSheet1.Range("D49").Value = "NONE"
            GoTo exitSub
SetPBM:
            wksSheet1.Range("D49").Value = "NONE"
            GoTo exitSub
SetPBCM:
            GoTo exitSub
SetPC:
            wksSheet1.Range("D38").Value = "NONE"
            setRangeNA (baseOptRanges)
            wksSheet1.Range("G47:H47").Value = "Supplied by others; Installed by others"
            clearRange (motorOptRanges)
        End If
    End If
    
exitSub:
    Application.EnableEvents = True
    
End Sub

Private Sub setRangeNA(targetRange As Variant)
    If Not initialized Then
        Call InitializeVariables
    End If
    
    For Each rng In targetRange
        wksSheet1.Range(rng).Value = "N/A"
    Next
End Sub

Private Sub clearRange(targetRange As Variant)
    If Not initialized Then
        Call InitializeVariables
    End If
    
    For Each rng In targetRange
        wksSheet1.Range(rng).ClearContents
    Next
End Sub

Private Sub writeToRange(targetSheet As Worksheet, targetRange As Variant, vals As Variant)
    For i = 0 To UBound(targetRange)
        targetSheeet.Range(targetRange(i)).Value = "'" & vals(i)
    Next
End Sub

Function reverseResults(arr As Variant) As Variant
    For r = 0 To UBound(arr, 1)
        i = LBound(arr, 2)
        j = UBound(arr, 2)
        Do While i < j
            temp = arr(r, i)
            arr(r, i) = arr(r, j)
            arr(r, j) = temp
            i = i + 1
            j = j - 1
        Loop
    Next
    reverseResults = arr
End Function
