Attribute VB_Name = "Module2"

Sub numberBaseplates()

'    Dim seriesList() As Variant
'    Dim dict As New Scripting.Dictionary
'    Dim results() As Variant
'    Dim tempRow() As Variant
'    Dim rng As Range
'    Dim optRanges As Variant
'    Dim targetSheet As Worksheet
'    Dim list1 As Variant, list2 As Variant, list3 As Variant, list4 As Variant, list5 As Variant, list6 As Variant, list7 As Variant, list8 As Variant, list9 As Variant, list10 As Variant
'    ReDim list1(0)
'    ReDim list2(0)
'    ReDim list3(0)
'    ReDim list4(0)
'    ReDim list5(0)
'    ReDim list6(0)
'    ReDim list7(0)
'    ReDim list8(0)
'    ReDim list9(0)
'    ReDim list10(0)
'
''    ReDim results(0, 12)
'    startTime = Timer
'    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Baseplate Numbering")
'
'    maxRows = 500000
'    lastRow = Cells(Rows.Count, 2).End(xlUp).Row
'    If lastRow > 16 Then targetSheet.Range("B16:M" & lastRow + 1).ClearContents
'
'    optRanges = targetSheet.Range("O3:W4").Value
'
'    Application.ScreenUpdating = False
'    With Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Constraints")
'        .Activate
'        seriesList = Range("B4:B39").Value
'        On Error GoTo err
'        For s = 1 To UBound(seriesList)
'
'            ' Create list of valid options from Constraints tables
'            For l = 1 To UBound(optRanges, 2)
'                tempHeader = Range(optRanges(1, l) & "3" & optRanges(2, l) & "3")
'                x = 0
'                ReDim Preserve tempRow(x)
'                Set rng = Range(optRanges(1, l) & s + 3 & optRanges(2, l) & s + 3)
'                N = WorksheetFunction.CountIf(rng, "<>")
'                For c = 0 To UBound(tempHeader, 2)
''                    Test = Columns(optRanges(1, l)).Column
'                    Set cell = Cells(s + 3, c + Columns(optRanges(1, l)).Column)
'                    If cell <> "" And x < N Then
'                        tempRow(x) = Cells(3, c + Columns(optRanges(1, l)).Column).Value
'                        x = x + 1
'                        If x < N Then ReDim Preserve tempRow(0 To x)
'                    End If
'                Next
'                Select Case l
'                    Case 1
'                        ReDim list1(0 To UBound(tempRow))
'                        list1 = tempRow
'                    Case 2
'                        ReDim list2(0 To UBound(tempRow))
'                        list2 = tempRow
'                    Case 3
'                        ReDim list3(0 To UBound(tempRow))
'                        list3 = tempRow
'                    Case 4
'                        ReDim list4(0 To UBound(tempRow))
'                        list4 = tempRow
'                    Case 5
'                        ReDim list5(0 To UBound(tempRow))
'                        list5 = tempRow
'                    Case 6
'                        ReDim list6(0 To UBound(tempRow))
'                        list6 = tempRow
'                    Case 7
'                        ReDim list7(0 To UBound(tempRow))
'                        list7 = tempRow
'                    Case 8
'                        ReDim list8(0 To UBound(tempRow))
'                        list8 = tempRow
'                    Case 9
'                        ReDim list9(0 To UBound(tempRow))
'                        list9 = tempRow
'                    Case 10
'                        ReDim list10(0 To UBound(tempRow))
'                        list10 = tempRow
'                End Select
'            Next
'
'            ' Create list of combinations using dictionary object
'            For Each a In list1
'                For Each b In list2
'                    For Each c In list3
'                        For Each d In list4
'                            For Each e In list5
'                                For Each f In list6
'                                    For Each g In list7
'                                        For Each h In list8
'                                            For Each i In list9
'                                                For Each j In list10
'
'                                                    ' Wet end unique checks
'                                                    If a = "NONE" Then
'                                                        b = "N/A"
'                                                        c = "N/A"
'                                                        d = "N/A"
'                                                        e = "N/A"
'                                                        g = "N/A"
'                                                        h = "N/A"
'                                                        i = "N/A"
'                                                    End If
'
'                                                    ' Add combination to dictionary object
'                                                    tempStr = a & "*" & b & "*" & c & "*" & d & "*" & e & "*" & f & "*" & g & "*" & h & "*" & i
'                                                    Do While Right(tempStr, 1) = "*"
'                                                        tempStr = Left(tempStr, Len(tempStr) - 1)
'                                                    Loop
'                                                    If Not (dict.Exists(tempStr)) Then
'                                                        dict.Add tempStr, dict.Count + 1
'                                                    End If
'                                                    If dict.Count + 1 > maxRows Then
'                                                        GoTo Done
'                                                    ElseIf dict.Count Mod 10000 = 0 Then
'                                                        DoEvents
'                                                    End If
'                                                Next j
'                                            Next i
'                                        Next h
'                                    Next g
'                                Next f
'                            Next e
'                        Next d
'                    Next c
'                Next b
'            Next a
'        Next
'    End With
'Done:
'
'    ReDim results(1 To dict.Count, 1 To UBound(optRanges, 2) + 2)
'    numRows = UBound(results, 1)
'    Erase tempRow
'    Erase seriesList
'    Erase optRanges
'
'    i = 0
'    For Each k In dict.Keys
'        i = i + 1
'        temp = Split(k, "*")
'        results(i, 1) = dict(k)
'        For j = 0 To UBound(temp)
'            results(i, j + 2) = temp(j)
'        Next
'        results(i, UBound(results, 2)) = k
'    Next k
'
'    With targetSheet
'        .Activate
'        .Range("B16:M" & 16 + dict.Count - 1) = results
'        .Range("R13").Value = dict.Count
'    End With
'    Application.ScreenUpdating = True
'    MsgBox "Time taken:" & Round(Timer - startTime, 2) & "seconds"
'    Exit Sub
'err:
'    Erase tempRow
'    Erase seriesList
'    Erase optRanges
'    MsgBox err.Number & ": " & err.Description
'    Application.ScreenUpdating = True
End Sub

Sub numberWetEnd()
    
    Dim maxRows As Long
    Dim seriesList() As Variant
    Dim dict As New Scripting.Dictionary
    Dim results() As Variant
    Dim tempRow() As Variant
    Dim rng As Range
    Dim optRanges As Variant
    Dim targetSheet As Worksheet
    Dim tbl As ListObject
    Dim list1 As Variant, list2 As Variant, list3 As Variant, list4 As Variant, list5 As Variant, list6 As Variant, list7 As Variant, list8 As Variant, list9 As Variant, list10 As Variant, list11 As Variant, list12 As Variant
    ReDim list1(0)
    ReDim list2(0)
    ReDim list3(0)
    ReDim list4(0)
    ReDim list5(0)
    ReDim list6(0)
    ReDim list7(0)
    ReDim list8(0)
    ReDim list9(0)
    ReDim list10(0)
    ReDim list11(0)
    ReDim list12(0)
    
'    ReDim results(0, 12)
    startTime = Timer
    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Wet End Numbering")
    Set tbl = targetSheet.ListObjects("Table100")

    maxRows = 500000
    
    lastRow = Cells(Rows.Count, 2).End(xlUp).Row
    If lastRow > 16 Then targetSheet.Range("B16:O" & lastRow + 1).ClearContents
    
    optRanges = targetSheet.Range("Q3:AB4").Value

    Application.ScreenUpdating = False
    With Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Constraints")
        .Activate
        seriesList = Range("B4:B39").Value
        On Error GoTo err
        For s = 1 To UBound(seriesList)
        
            ' Create list of valid options from Constraints tables
            For l = 1 To UBound(optRanges, 2)
                tempHeader = Range(optRanges(1, l) & "3" & optRanges(2, l) & "3")
                x = 0
                ReDim Preserve tempRow(x)
                Set rng = Range(optRanges(1, l) & s + 3 & optRanges(2, l) & s + 3)
                n = WorksheetFunction.CountIf(rng, "<>")
                For c = 0 To UBound(tempHeader, 2)
'                    Test = Columns(optRanges(1, l)).Column
                    Set cell = Cells(s + 3, c + Columns(optRanges(1, l)).Column)
                    If cell <> "" And x < n Then
                        tempRow(x) = Cells(3, c + Columns(optRanges(1, l)).Column).Value
                        x = x + 1
                        If x < n Then ReDim Preserve tempRow(0 To x)
                    End If
                Next
                Select Case l
                    Case 1
                        ReDim list1(0 To UBound(tempRow))
                        list1 = tempRow
                    Case 2
                        ReDim list2(0 To UBound(tempRow))
                        list2 = tempRow
                    Case 3
                        ReDim list3(0 To UBound(tempRow))
                        list3 = tempRow
                    Case 4
                        ReDim list4(0 To UBound(tempRow))
                        list4 = tempRow
                    Case 5
                        ReDim list5(0 To UBound(tempRow))
                        list5 = tempRow
                    Case 6
                        ReDim list6(0 To UBound(tempRow))
                        list6 = tempRow
                    Case 7
                        ReDim list7(0 To UBound(tempRow))
                        list7 = tempRow
                    Case 8
                        ReDim list8(0 To UBound(tempRow))
                        list8 = tempRow
                    Case 9
                        ReDim list9(0 To UBound(tempRow))
                        list9 = tempRow
                    Case 10
                        ReDim list10(0 To UBound(tempRow))
                        list10 = tempRow
                    Case 11
                        ReDim list11(0 To UBound(tempRow))
                        list11 = tempRow
                    Case 12
                        ReDim list12(0 To UBound(tempRow))
                        list12 = tempRow
                End Select
            Next
            
            ' Create list of combinations using dictionary object
            For Each a In list1
                For Each b In list2
                    For Each c In list3
                        For Each d In list4
                            For Each e In list5
                                For Each f In list6
                                    For Each g In list7
                                        For Each h In list8
                                            For Each i In list9
                                                For Each j In list10
                                                    For Each k In list11
                                                        For Each l In list12
                                                    
                                                            ' Wet end unique checks
'                                                            If b = "NONE" And k = "NONE" Then
'                                                                c = "N/A"
'                                                                d = "N/A"
'                                                                e = "N/A"
'                                                                f = "N/A"
'                                                                l = "N/A"
'
                                                            If b = "NONE" Then
                                                                c = "N/A"
                                                                d = "N/A"
                                                                e = "N/A"
                                                                f = "N/A"
'                                                            ElseIf k = "NONE" Then
                                                                
                                                            End If
                                                            
                                                            ' Add combination to dictionary object
                                                            tempStr = a & "*" & b & "*" & c & "*" & d & "*" & e & "*" & f & "*" & g & "*" & h & "*" & i & "*" & j & "*" & k & "*" & l
                                                            Do While Right(tempStr, 1) = "*"
                                                                tempStr = Left(tempStr, Len(tempStr) - 1)
                                                            Loop
                                                            If Not (dict.Exists(tempStr)) And Not (InStr(tempStr, "Custom") > 0) Then
                                                                dict.Add tempStr, dict.Count + 1
                                                            End If
                                                            If dict.Count + 1 > maxRows Then
                                                                GoTo Done
                                                            ElseIf dict.Count Mod 10000 = 0 Then
                                                                DoEvents
                                                            End If
                                                        Next l
                                                    Next k
                                                Next j
                                            Next i
                                        Next h
                                    Next g
                                Next f
                            Next e
                        Next d
                    Next c
                Next b
            Next a
        Next
    End With
Done:

    ReDim results(1 To dict.Count, 1 To UBound(optRanges, 2) + 2)
    numRows = UBound(results, 1)
    Erase tempRow
    Erase seriesList
    Erase optRanges
    
    i = 0
    For Each k In dict.Keys
        i = i + 1
        temp = Split(k, "*")
        results(i, 1) = dict(k)
        For j = 0 To UBound(temp)
            results(i, j + 2) = temp(j)
        Next
        results(i, UBound(results, 2)) = k
    Next k
    
    With targetSheet
        .Activate
        .Range("B16:O" & 16 + dict.Count - 1) = results
        .Range("B13").Value = dict.Count
    End With
    tbl.Resize tbl.Range.CurrentRegion
    Application.ScreenUpdating = True
    MsgBox "Time taken:" & Round(Timer - startTime, 2) & "seconds"
    Exit Sub
err:
    Erase tempRow
    Erase seriesList
    Erase optRanges
    MsgBox err.Number & ": " & err.Description
    Application.ScreenUpdating = True
End Sub

Sub numberImpellerOpts()
    Dim maxRows As Long
    Dim seriesList() As Variant
    Dim dict As New Scripting.Dictionary
    Dim results() As Variant
    Dim tempRow() As Variant
    Dim rng As Range
    Dim optRanges As Variant
    Dim targetSheet As Worksheet
    Dim tbl As ListObject
    Dim list1 As Variant, list2 As Variant, list3 As Variant, list4 As Variant
    ReDim list1(0)
    ReDim list2(0)
    ReDim list3(0)
'    ReDim list4(0)
    
'    ReDim results(0, 12)
    startTime = Timer
    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Wet End Numbering")
    Set tbl = targetSheet.ListObjects("Table106")
    list4 = Array("Not Required", "Required")

    maxRows = 500000
    
    lastRow = Cells(Rows.Count, 2).End(xlUp).Row
    If lastRow > 16 Then targetSheet.Range("AE16:AK" & lastRow + 1).ClearContents
    
    optRanges = targetSheet.Range("AM3:AP4").Value
    dict.Add "NONE*N/A*N/A*N/A", 0

    Application.ScreenUpdating = False
    With Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Constraints")
        .Activate
        seriesList = Range("B4:B39").Value
        On Error GoTo err
        For s = 1 To UBound(seriesList)
        
            ' Create list of valid options from Constraints tables
            For l = 1 To UBound(optRanges, 2) - 1
                tempHeader = Range(optRanges(1, l) & "3" & optRanges(2, l) & "3")
                x = 0
                ReDim Preserve tempRow(x)
                Set rng = Range(optRanges(1, l) & s + 3 & optRanges(2, l) & s + 3)
                n = WorksheetFunction.CountIf(rng, "<>")
                For c = 0 To UBound(tempHeader, 2)
'                    Test = Columns(optRanges(1, l)).Column
                    Set cell = Cells(s + 3, c + Columns(optRanges(1, l)).Column)
                    If cell <> "" And x < n Then
                        tempRow(x) = Cells(3, c + Columns(optRanges(1, l)).Column).Value
                        x = x + 1
                        If x < n Then ReDim Preserve tempRow(0 To x)
                    End If
                Next
                Select Case l
                    Case 1
                        ReDim list1(0 To UBound(tempRow))
                        list1 = tempRow
                    Case 2
                        ReDim list2(0 To UBound(tempRow))
                        list2 = tempRow
                    Case 3
                        ReDim list3(0 To UBound(tempRow))
                        list3 = tempRow
                    Case 4
'                        ReDim list4(0 To UBound(tempRow))
'                        list4 = tempRow
                End Select
            Next
            
            ' Create list of combinations using dictionary object
            For Each a In list1
                For Each b In list2
                    For Each c In list3
                        For Each d In list4
                            If a <> "NONE" Then
                                ' Add combination to dictionary object
                                tempStr = a & "*" & b & "*" & c & "*" & d
                                Do While Right(tempStr, 1) = "*"
                                    tempStr = Left(tempStr, Len(tempStr) - 1)
                                Loop
                                If Not (dict.Exists(tempStr)) Then
                                    dict.Add tempStr, dict.Count
                                End If
                                If dict.Count + 1 > maxRows Then
                                    GoTo Done
                                ElseIf dict.Count Mod 10000 = 0 Then
                                    DoEvents
                                End If
                            End If
                        Next d
                    Next c
                Next b
            Next a
        Next
    End With
Done:

    ReDim results(1 To dict.Count, 1 To UBound(optRanges, 2) + 2)
    numRows = UBound(results, 1)
    Erase tempRow
    Erase seriesList
    Erase optRanges
    
    i = 0
    For Each k In dict.Keys
        i = i + 1
        temp = Split(k, "*")
        results(i, 1) = dict(k)
        For j = 0 To UBound(temp)
            results(i, j + 2) = temp(j)
        Next
        results(i, UBound(results, 2)) = k
    Next k
    
    With targetSheet
        .Activate
        .Range("AE16:AJ" & 16 + dict.Count - 1) = results
        .Range("AE13").Value = dict.Count
    End With
    tbl.Resize tbl.Range.CurrentRegion
    Application.ScreenUpdating = True
    MsgBox "Time taken:" & Round(Timer - startTime, 2) & "seconds"
    Exit Sub
err:
    Erase tempRow
    Erase seriesList
    Erase optRanges
    MsgBox err.Number & ": " & err.Description
    Application.ScreenUpdating = True

End Sub

Sub numberPowerEnd()

    Dim maxRows As Long
    Dim seriesList() As Variant
    Dim dict As New Scripting.Dictionary
    Dim results() As Variant
    Dim tempRow() As Variant
    Dim rng As Range
    Dim optRanges As Variant
    Dim targetSheet As Worksheet
    Dim tbl As ListObject
    Dim list1 As Variant, list2 As Variant, list3 As Variant, list4 As Variant, list5 As Variant, list6 As Variant, list7 As Variant, list8 As Variant, list9 As Variant, list10 As Variant, list11 As Variant
    ReDim list1(0)
    ReDim list2(0)
    ReDim list3(0)
    ReDim list4(0)
    ReDim list5(0)
    ReDim list6(0)
    ReDim list7(0)
    ReDim list8(0)
    ReDim list9(0)
    ReDim list10(0)
    ReDim list11(0)
    
'    ReDim results(0, 12)
    startTime = Timer
    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Power End Numbering")
    Set tbl = targetSheet.ListObjects("Table101")

    maxRows = 1000
    lastRow = Cells(Rows.Count, 2).End(xlUp).Row
    If lastRow > 16 Then targetSheet.Range("B16:N" & lastRow + 1).ClearContents
    
    optRanges = targetSheet.Range("Q3:AA4").Value

    Application.ScreenUpdating = False
    With Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Constraints")
        .Activate
        seriesList = Range("B4:B39").Value
        On Error GoTo err
        For s = 1 To UBound(seriesList)
        
            ' Create list of valid options from Constraints tables
            For l = 1 To UBound(optRanges, 2)
                tempHeader = Range(optRanges(1, l) & "3" & optRanges(2, l) & "3")
                x = 0
                ReDim tempRow(x)
                Set rng = Range(optRanges(1, l) & s + 3 & optRanges(2, l) & s + 3)
                n = WorksheetFunction.CountIf(rng, "<>")
                For c = 0 To UBound(tempHeader, 2)
'                    Test = Columns(optRanges(1, l)).Column
                    Set cell = Cells(s + 3, c + Columns(optRanges(1, l)).Column)
                    If cell <> "" And x < n Then
                        tempRow(x) = Cells(3, c + Columns(optRanges(1, l)).Column).Value
                        x = x + 1
                        If x < n Then ReDim Preserve tempRow(0 To x)
                    End If
                Next
                Select Case l
                    Case 1
                        ReDim list1(0 To UBound(tempRow))
                        list1 = tempRow
                    Case 2
                        ReDim list2(0 To UBound(tempRow))
                        list2 = tempRow
                    Case 3
                        ReDim list3(0 To UBound(tempRow))
                        list3 = tempRow
                    Case 4
                        ReDim list4(0 To UBound(tempRow))
                        list4 = tempRow
                    Case 5
                        ReDim list5(0 To UBound(tempRow))
                        list5 = tempRow
                    Case 6
                        ReDim list6(0 To UBound(tempRow))
                        list6 = tempRow
                    Case 7
                        ReDim list7(0 To UBound(tempRow))
                        list7 = tempRow
                    Case 8
                        ReDim list8(0 To UBound(tempRow))
                        list8 = tempRow
                    Case 9
                        ReDim list9(0 To UBound(tempRow))
                        list9 = tempRow
                    Case 10
                        ReDim list10(0 To UBound(tempRow))
                        list10 = tempRow
                    Case 11
                        ReDim list11(0 To UBound(tempRow))
                        list11 = tempRow
                End Select
            Next
            
            ' Create list of combinations using dictionary object
            For Each a In list1
                For Each b In list2
                    For Each c In list3
                        For Each d In list4
                            For Each e In list5
                                For Each f In list6
                                    For Each g In list7
                                        For Each h In list8
                                            For Each i In list9
                                                For Each j In list10
                                                    For Each k In list11
                                                    
                                                        ' Power end unique checks
    
    
                                                        ' Add combination to dictionary object
                                                        tempStr = a & "*" & b & "*" & c & "*" & d & "*" & e & "*" & f & "*" & g & "*" & h & "*" & i & "*" & j & "*" & k
                                                        Do While Right(tempStr, 1) = "*"
                                                            tempStr = Left(tempStr, Len(tempStr) - 1)
                                                        Loop
                                                        If Not (dict.Exists(tempStr)) And Not (InStr(tempStr, "Custom") > 0) Then
                                                            dict.Add tempStr, dict.Count
                                                        End If
                                                        If dict.Count + 1 > maxRows Then
                                                            GoTo Done
                                                        ElseIf dict.Count Mod 10000 = 0 Then
                                                            DoEvents
                                                        End If
                                                    Next k
                                                Next j
                                            Next i
                                        Next h
                                    Next g
                                Next f
                            Next e
                        Next d
                    Next c
                Next b
            Next a
        Next
    End With
Done:

    ReDim results(1 To dict.Count, 1 To UBound(optRanges, 2) + 2)
    numRows = UBound(results, 1)
    Erase tempRow
    Erase seriesList
    Erase optRanges
    
    i = 0
    For Each k In dict.Keys
        i = i + 1
        temp = Split(k, "*")
        results(i, 1) = dict(k)
        For j = 0 To UBound(temp)
            results(i, j + 2) = temp(j)
        Next
        results(i, UBound(results, 2)) = k
    Next k
    
    With targetSheet
        .Activate
        .Range("B16:N" & 16 + dict.Count - 1) = results
        .Range("T13").Value = dict.Count
    End With
    tbl.Resize tbl.Range.CurrentRegion
    Application.ScreenUpdating = True
    MsgBox "Time taken:" & Round(Timer - startTime, 2) & "seconds"
    Exit Sub
err:
    Erase tempRow
    Erase seriesList
    Erase optRanges
    MsgBox err.Number & ": " & err.Description
    Application.ScreenUpdating = True
End Sub

Sub numberTesting()

    Dim results() As Variant
    Dim targetSheet As Worksheet
    Dim tbl As ListObject
    
    startTime = Timer
    
    Application.ScreenUpdating = False
    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Test and Doc Numbering")
    Set tbl = targetSheet.ListObjects("Table108")
    
    perfs = targetSheet.Range("C3:C7")
    hydros = targetSheet.Range("D3:D5")
    genInspections = targetSheet.Range("E3:E6")
    vibes = targetSheet.Range("F3:F4")
    soundLevels = targetSheet.Range("G3:G4")
    
    numRows = UBound(perfs, 1) * UBound(hydros, 1) * UBound(genInspections, 1) * UBound(vibes, 1) * UBound(soundLevels, 1)
    ReDim results(1 To numRows, 1 To 8)
    
    ctr = 1
    For Each perf In perfs
        For Each hydro In hydros
            For Each gen In genInspections
                For Each vib In vibes
                    For Each sound In soundLevels
                                        
                        ' Add combination to dictionary object
                        results(ctr, 1) = ctr - 1
                        results(ctr, 2) = perf
                        results(ctr, 3) = hydro
                        results(ctr, 4) = gen
                        results(ctr, 5) = vib
                        results(ctr, 6) = sound
                        results(ctr, 7) = Application.WorksheetFunction.Base(ctr - 1, 36, 2)
                        results(ctr, 8) = perf & "*" & hydro & "*" & gen & "*" & vib & "*" & sound
                        ctr = ctr + 1
                    Next sound
                Next vib
            Next gen
        Next hydro
    Next perf

Done:

    With targetSheet
        .Activate
        .Range("B16:I" & 16 + numRows - 1) = results
        .Range("E13").Value = numRows
    End With
    tbl.Resize tbl.Range.CurrentRegion
    Application.ScreenUpdating = True
    MsgBox "Time taken:" & Round(Timer - startTime, 2) & "seconds"
    Exit Sub
err:
    MsgBox err.Number & ": " & err.Description
    Application.ScreenUpdating = True
End Sub

Sub numberDocumentation()

    Dim results() As Variant
    Dim targetSheet As Worksheet
    Dim tbl As ListObject
    Dim dict As New Scripting.Dictionary
    
    startTime = Timer
    
    Application.ScreenUpdating = False
    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Test and Doc Numbering")
    Set tbl = targetSheet.ListObjects("Table109")
    
    docs = targetSheet.Range("U3:U48")
    maxRows = 10000000
    
    For Each d1 In docs
        For Each d2 In docs
            For Each d3 In docs
                For Each d4 In docs
                                        
                    ' Check for repeated documentation selections
                    If Not ((d1 = d2 And d1 <> "NONE") Or (d1 = d3 And d1 <> "NONE") Or (d1 = d4 And d1 <> "NONE") Or (d2 = d3 And d2 <> "NONE") Or (d2 = d4 And d2 <> "NONE") Or (d3 = d4 And d3 <> "NONE")) Then
                        tempStr = d1 & "*" & d2 & "*" & d3 & "*" & d4
                        If Not (dict.Exists(tempStr)) Then
                            dict.Add tempStr, dict.Count + 1
                        End If
                        If dict.Count + 1 > maxRows Then GoTo Done
                        If dict.Count Mod 10000 = 0 Then DoEvents
                    End If
                Next d4
            Next d3
        Next d2
    Next d1

Done:

    ReDim results(1 To dict.Count, 1 To 7)
    
    i = 1
    For Each k In dict.Keys
        temp = Split(k, "*")
        results(i, 1) = dict.Item(k)
        results(i, 2) = temp(0)
        results(i, 3) = temp(1)
        results(i, 4) = temp(2)
        results(i, 5) = temp(3)
        results(i, 6) = Application.WorksheetFunction.Base(i, 36, 5)
        results(i, 7) = k
        i = i + 1
    Next
        
    With targetSheet
        .Activate
        .Range("L16:R" & 16 + dict.Count - 2) = results
        .Range("N13").Value = dict.Count
    End With
    tbl.Resize tbl.Range.CurrentRegion
    Application.ScreenUpdating = True
    MsgBox "Time taken:" & Round(Timer - startTime, 2) & "seconds"
    Exit Sub
err:
    MsgBox err.Number & ": " & err.Description
    Application.ScreenUpdating = True
End Sub

Sub numberAdditionalOptions()
    
    Dim results() As Variant
    Dim targetSheet As Worksheet
    Dim tbl As ListObject
    
    Application.ScreenUpdating = False
    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Misc Numbering")
    Set tbl = targetSheet.ListObjects("Table105")
    
    targetSheet.Activate
    
    shippingGasket = targetSheet.Range("J3:J4")
    auxNameplate = targetSheet.Range("K3:K4")
    crating = targetSheet.Range("L3:L7")
    paintOpts = targetSheet.Range("M3:M7")
    coats = targetSheet.Range("N3:N4")
    
    numRows = UBound(shippingGasket) * UBound(auxNameplate) * UBound(crating) * UBound(paintOpts) * UBound(coats)
    ReDim results(numRows, 8)
    
    ctr = 0
    For Each sg In shippingGasket
        For Each an In auxNameplate
            For Each crate In crating
                For Each paint In paintOpts
                    For Each coat In coats
                        tempStr = sg & "*" & an & "*" & crate & "*" & paint & "*" & coat
                        If Not (InStr(tempStr, "Custom") > 0) Then
                            results(ctr, 0) = ctr + 1
                            results(ctr, 1) = sg
                            results(ctr, 2) = an
                            results(ctr, 3) = crate
                            results(ctr, 4) = paint
                            results(ctr, 5) = coat
                            results(ctr, 6) = Application.WorksheetFunction.Base(ctr, 36, 2)
                            results(ctr, 7) = sg & "*" & an & "*" & crate & "*" & paint & "*" & coat
                            ctr = ctr + 1
                        End If
                    Next coat
                Next paint
            Next crate
        Next an
    Next sg
    
    targetSheet.Range("I20:P" & numRows + 1) = results
    tbl.Resize tbl.Range.CurrentRegion
    Application.ScreenUpdating = True
End Sub

Sub numberCoolingPlans()
    Dim results() As Variant
    Dim targetSheet As Worksheet
    Dim tbl As ListObject
    
    Application.ScreenUpdating = False
    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Misc Numbering")
    Set tbl = targetSheet.ListObjects("Table104")
    
    targetSheet.Activate
    
    shippingGasket = targetSheet.Range("C4:C16")
    auxNameplate = targetSheet.Range("D3:D6")
    crating = targetSheet.Range("E3:E6")
    
    numRows = UBound(shippingGasket) * UBound(auxNameplate) * UBound(crating)
    ReDim results(numRows, 5)
    results(0, 0) = "1"
    results(0, 1) = "NONE"
    results(0, 2) = "N/A"
    results(0, 3) = "N/A"
    results(0, 4) = "00"
    results(0, 5) = "NONE*N/A*N/A"
    
    ctr = 1
    For Each sg In shippingGasket
        For Each an In auxNameplate
            For Each crate In crating
                results(ctr, 0) = ctr + 1
                results(ctr, 1) = sg
                results(ctr, 2) = an
                results(ctr, 3) = crate
                results(ctr, 4) = Application.WorksheetFunction.Base(ctr, 36, 2)
                results(ctr, 5) = sg & "*" & an & "*" & crate
                ctr = ctr + 1
            Next
        Next
    Next
    
    targetSheet.Range("B20:G" & numRows + 1) = results
    tbl.Resize tbl.Range.CurrentRegion
    Application.ScreenUpdating = True
End Sub

Sub numberMotors()

    Dim results() As Variant
    Dim sourceSheet As Worksheet
    Dim targetSheet As Worksheet
    Dim tbl As ListObject
    Dim tempRow() As Variant
    Dim ratingTable As Range
    Dim frameStyleTable As Range
    Dim rng As Range
    Dim dict As New Scripting.Dictionary
    
    startTime = Timer
    
    Application.ScreenUpdating = False
    Set targetSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Motor Numbering")
    Set sourceSheet = Workbooks("Dean Data Sheet Rev 2.xlsm").Sheets("Motor Constraints")
    Set tbl = targetSheet.ListObjects("Table110")
    tbl.DataBodyRange.ClearContents
    
    targetSheet.Activate
    maxRows = 1000000
    
'    inclusion = Array(targetSheet.Range("C3"), targetSheet.Range("C5"))
    driveOpts = targetSheet.Range("D3:D4")
'    voltages = targetSheet.Range("H3:H17")
    enclosureOpts = targetSheet.Range("K3:K7")
'    efficiencies = targetSheet.Range("L3")
'    cFace = targetSheet.Range("M3:M4")
    brand = targetSheet.Range("M3:M4")
    Set ratingTable = sourceSheet.Range("Motor_Frame_Ratings_Table")
    Set frameStyleTable = sourceSheet.Range("B29:I48")
    sizeCol = sourceSheet.Range("B29:B48")
    
    ctr = 1
    For p = 2 To ratingTable.Rows.Count - 3
        For s = 2 To ratingTable.Columns.Count - 1
            If ratingTable.Item(p, s) <> "" Then
                frameList = ""
                frameSizeArr = Split(ratingTable.Item(p, s), ", ")
                For Each frameSize In frameSizeArr
                    frameSize = Left(frameSize, 3)
                    r = Application.Match(frameSize, sizeCol, 0)
                    For col = 2 To frameStyleTable.Columns.Count
                        If frameStyleTable.Item(r, col) <> "" Then frameList = frameList & frameSize & frameStyleTable.Item(1, col) & ", "
                    Next
'                    frameList = frameList & ";"
                Next
                frameList = Left(frameList, Len(frameList) - 2)
                numPoles = ratingTable.Item(ratingTable.Rows.Count - 2, s)
                freqs = Split(ratingTable.Item(ratingTable.Rows.Count - 1, s), ", ")
                tempArr = Split(ratingTable.Item(ratingTable.Rows.Count, s), "; ")
                f = 0
                For Each freq In freqs
                    voltages = Split(tempArr(f), ", ")
                    For Each voltage In voltages
'                        For Each a In inclusion
                            For Each b In driveOpts
                                For Each c In enclosureOpts
'                                    For Each d In efficiencies
                                        For Each e In brand
                                            tempStr = targetSheet.Range("C3") & "*" & b & "*" & frameList & "*" & ratingTable.Item(1, s) & "*" & ratingTable.Item(p, 1) & "*" & voltage & "*" & freq & "*" & _
                                                      numPoles & "*" & c & "*" & targetSheet.Range("L3") & "*" & e

                                            If Not (dict.Exists(tempStr)) Then
                                                dict.Add tempStr, dict.Count + 1
                                                If dict.Count + 1 > maxRows Then GoTo Done
                                                If dict.Count Mod 10000 = 0 Then DoEvents
                                            End If
                                        Next
'                                    Next
                                Next
                            Next
'                        Next
                    Next
                    f = f + 1
                Next
            End If
        Next
    Next
    
'    ctr = 1
'
'    For p = 2 To ratingTable.Rows.Count - 3
'        For s = 2 To ratingTable.Columns.Count - 1
'            If ratingTable.Item(p, s) <> "" Then
'                frameSizeArr = Split(ratingTable.Item(p, s), ", ")
'                numPoles = ratingTable.Item(ratingTable.Rows.Count - 2, s)
'                freqs = Split(ratingTable.Item(ratingTable.Rows.Count - 1, s), ", ")
'                tempArr = Split(ratingTable.Item(ratingTable.Rows.Count, s), "; ")
'                For Each frameSize In frameSizeArr
'                    frameSize = Left(frameSize, 3)
'                    r = Application.Match(frameSize, sizeCol, 0)
'                    For col = 2 To frameStyleTable.Columns.Count
'                        If frameStyleTable.Item(r, col) <> "" Then
'                            motorFrame = frameSize & frameStyleTable.Item(1, col)
'                            f = 0
'                            For Each freq In freqs
'                                voltages = Split(tempArr(f), ", ")
'                                For Each voltage In voltages
''                                    For Each a In inclusion
'                                        For Each b In driveOpts
'                                            For Each c In enclosureOpts
''                                                For Each d In efficiencies
'                                                    For Each e In brand
'                                                        tempStr = targetSheet.Range("C3") & "*" & b & "*" & motorFrame & "*" & ratingTable.Item(1, s) & "*" & ratingTable.Item(p, 1) & "*" & voltage & "*" & freq & "*" & _
'                                                                  numPoles & "*" & c & "*" & targetSheet.Range("L3").Value & "*" & e
'
'                                                        If Not (dict.Exists(tempStr)) Then
'                                                            dict.Add tempStr, dict.Count + 1
'                                                            If dict.Count + 1 > maxRows Then GoTo Done
'                                                            If dict.Count Mod 10000 = 0 Then DoEvents
'                                                        End If
'                                                    Next
''                                                Next
'                                            Next
'                                        Next
''                                    Next
'                                Next
'                                f = f + 1
'                            Next
'                        End If
'                    Next
'                Next
'            End If
'        Next
'    Next
    
Done:
    
    ReDim results(1 To dict.Count, 1 To 14)
    
    i = 1
    For Each k In dict.Keys
        temp = Split(k, "*")
        results(i, 1) = dict(k)
        For j = 0 To UBound(temp)
            results(i, j + 2) = temp(j)
        Next
        results(i, 13) = Application.WorksheetFunction.Base(dict(k), 36, 3)
        results(i, 14) = k
        i = i + 1
    Next
    
    targetSheet.Range("B21:O" & 21 + dict.Count - 1) = results
    targetSheet.Range("D18").Value = dict.Count
    tbl.Resize Range("B20:O" & 20 + dict.Count)
    Application.ScreenUpdating = True
    MsgBox "Time taken:" & Round(Timer - startTime, 2) & "seconds"
    Exit Sub
errHandler:

End Sub

Public Function reDimPreserve(ByVal aArray As Variant, ByVal newFirstUBound As Long, ByVal newLastUBound As Long) As Variant
    Dim tmpArr As Variant, nOldFirstUBound As Long, nOldLastUBound As Long, nFirst As Long, nLast As Long
    
    If Not IsArray(aArray) Then
        reDimPreserve = Array(Empty)
    ElseIf newFirstUBound < UBound(aArray, 1) Or newLastUBound < UBound(aArray, 2) Then
        reDimPreserve = Array(Empty)
    Else
        ReDim tmpArr(newFirstUBound, newLastUBound)
        nOldFirstUBound = UBound(aArray, 1)
        nOldLastUBound = UBound(aArray, 2)
        For nFirst = LBound(aArray, 1) To newFirstUBound
            For nLast = LBound(aArray, 2) To newLastUBound
                If nOldFirstUBound >= nFirst And nOldLastUBound >= nLast Then
                    tmpArr(nFirst, nLast) = aArray(nFirst, nLast)
                End If
            Next nLast
        Next nFirst
        reDimPreserve = tmpArr
        Erase tmpArr
    End If
End Function
