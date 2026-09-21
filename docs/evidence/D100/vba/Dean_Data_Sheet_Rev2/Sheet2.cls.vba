Attribute VB_Name = "Sheet2"
Attribute VB_Base = "0{00020820-0000-0000-C000-000000000046}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = True
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = True
Attribute VB_Control = "CreatePDF, 9, 0, MSForms, CommandButton"
Attribute VB_Control = "SaveToDatabase, 10, 1, MSForms, CommandButton"
Attribute VB_Control = "ClearQuote, 11, 2, MSForms, CommandButton"
Private Sub ClearQuote_Click()
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False
    
    For Each rng In quoteRanges
        If Left(rng, 1) <> "H" Then
            wksSheet2.Range(rng).ClearContents
        End If
    Next
        
    Application.EnableEvents = True
End Sub

Private Sub CreatePDF_Click()
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False
    
    Dim wksAllSheets As Variant
    Dim strFilename As String, strFilepath As String
    Dim strTempFile As String
    Dim strUsername As String
    Dim fdObj As Object
    Dim primaryDoc As Object
    Dim TsCs As Object
    Dim app As Object
    Dim avDoc As Object
    Dim quit As Integer
    
    If wksSheet2.Range("B3").Value = "ENTER A NEW DISTRIBUTOR" Or wksSheet2.Range("B3").Value = "SELECT A DISTRIBUTOR" Or wksSheet2.Range("B3").Value = "" Then
        MsgBox "Please select or create one from the list and try again.", vbCritical, "ERROR: You must select a customer!"
        GoTo CleanExit
    End If
    
    If wksSheet2.Range("C5").Value = "" Then
        resp = MsgBox("Would you like to continue anyways?", vbYesNo, "WARNING: Quote number field is empty!")
        If resp <> vbYes Then GoTo CleanExit
    End If
    
    If wksSheet2.Range("B54").Value = "ENTER A NEW AE" Or wksSheet2.Range("B54").Value = "SELECT AN AE" Or wksSheet2.Range("B54").Value = "" Then
        MsgBox "Please select or create one from the list and try again.", vbCritical, "ERROR: You must select a signature!"
        GoTo CleanExit
    End If
    
'    If IsEmpty(wksSheet2.Range("A3")) Or IsEmpty(wksSheet2.Range("B5")) Or IsEmpty(wksSheet2.Range("A54")) Then
'        response = MsgBox("One or more important pieces of information is missing. Check the Customer, Quote Number, and Signature fields." & vbCrLf & vbCrLf & _
'                          "Would you like to continue anyways?", vbYesNo, "WARNING")
'        If response = vbNo Then
'            GoTo CleanExit
'        End If
'    End If
    
    'Set references up-front
    wksAllSheets = Array("Data Sheet", "Formal Quote")
    'strUsername = Environ("USERNAME")
    strFilepath = "P:\Dean\DEAN_PROJECTS\Numbering Project\Quotes\" & wksSheet2.Range("B3").Value & "\"
    
    Application.ScreenUpdating = False
    Set fdObj = CreateObject("Scripting.FileSystemObject")
    If Not (fdObj.FolderExists(strFilepath)) Then
        fdObj.createfolder (strFilepath)
    End If
    Application.ScreenUpdating = True
    
    'Create the full Filename using quote information
    With wksSheet2
    strFilename = strFilepath & Range("C5").Value & "_" & _
                                Range("I5").Value & "_" & _
                                Range("C20").Value & "_" & _
                                Range("C21").Value & "_" & _
                                Range("B3").Value & "_" & _
                                "Formal Quote"
    End With
    
    If InStr(strFilename, "/") Then
        MsgBox "Remove the problem character(s) and try again.", vbExclamation
        GoTo CleanExit
    End If
    
    strTempFile = strFilename & "_UNMERGED.pdf"
    
    'Save the Array of worksheets (which will be selected) as a PDF
    ThisWorkbook.Sheets(wksAllSheets).Select
    On Error GoTo errHandler
    ActiveSheet.ExportAsFixedFormat _
              Type:=xlTypePDF, _
              Filename:=strTempFile, _
              Quality:=xlQualityStandard, _
              IncludeDocProperties:=True, _
              IgnorePrintAreas:=False, _
              OpenAfterPublish:=False
              
    'Make sure all the worksheets are NOT left selected
    wksSheet2.Select
    
    Set primaryDoc = CreateObject("AcroExch.PDDoc")
    If Not (primaryDoc.Open(strTempFile)) Then
        MsgBox "Error opening primary document at " & strTempFile
        GoTo CleanExit
    End If

    Set TsCs = CreateObject("AcroExch.PDDoc")
    If Not (TsCs.Open("P:\Dean\DEAN_PROJECTS\Numbering Project\TuskTs&Cs_11.18.25.pdf")) Then
        MsgBox "Error opening document P:\Dean\DEAN_PROJECTS\Numbering Project\TuskTs&Cs_11.18.25.pdf"
        GoTo CleanExit
    End If
    
    If Not primaryDoc.InsertPages(primaryDoc.GetNumPages - 1, TsCs, 0, TsCs.GetNumPages, False) Then
        MsgBox "Error merging files"
        GoTo CleanExit
    End If

    TsCs.Close: Set TsCs = Nothing
    primaryDoc.Save PDSaveFull, strFilename & ".pdf"
    primaryDoc.Close: Set primaryDoc = Nothing
    
    Set app = CreateObject("AcroExch.App")
    Set avDoc = CreateObject("AcroExch.AVDoc")
    If avDoc.Open(strFilename & ".pdf", "") Then
        avDoc.Maximize (True)
        app.Show
    Else
        MsgBox "Cannot open the PDF document."
    End If
    
CleanExit:
    If Not (strTempFile = "") Then Kill strTempFile
    If Not (primaryDoc Is Nothing) Then primaryDoc.Close: Set primaryDoc = Nothing
    If Not (TsCs Is Nothing) Then TsCs.Close: Set TsCs = Nothing
    If Not (app Is Nothing) Then app.Exit: Set app = Nothing
    Application.EnableEvents = True
    Exit Sub
errHandler:
    MsgBox err.Number & ": " & err.Description

End Sub

Private Sub SaveToDatabase_Click()
'    Dim Conn As Object, cmd As Object
'    Dim rs As Object
'    Dim sql As String
'    Dim SheetName As String
'    Dim colNames As String
'    Dim paramMarks As String
'    Dim vals() As Variant
'    ReDim vals(lenHeaders)
'
'    SheetName = "Custom Confs"
'
'    'Fill vals Array
'    ctr = 0
'    For i = 0 To UBound(dataSheetRanges)
'        If Not (IsEmpty(wksSheet1.Range(dataSheetRanges(i)))) Then
'            modifiedRange = dataSheetRanges(i)
'            If Len(modifiedRange) > 3 Then
'                modifiedRange = Left(modifiedRange, (Len(modifiedRange) - 1) / 2)
'            End If
'            vals(ctr) = wksSheet1.Range(modifiedRange).value
'        Else
'            vals(ctr) = ""
'        End If
'        ctr = ctr + 1
'    Next i
'
'    For i = 0 To UBound(quoteRanges)
'        If Not (IsEmpty(wksSheet2.Range(quoteRanges(i)))) Then
'            modifiedRange = quoteRanges(i)
'            If Len(modifiedRange) > 3 Then
'                modifiedRange = Left(modifiedRange, (Len(modifiedRange) - 1) / 2)
'            End If
'            vals(ctr) = wksSheet2.Range(modifiedRange).value
'        Else
'            vals(ctr) = ""
'        End If
'        ctr = ctr + 1
'    Next i
'
'    vals(UBound(vals) - 1) = Environ("USERNAME")
'    vals(UBound(vals)) = Now
'
'    ' Open ADO connection to Excel workbook
'    Set Conn = CreateObject("ADODB.Connection")
'    Conn.Open "Provider=Microsoft.ACE.OLEDB.12.0;" & _
'              "Data Source=" & dbPath & ";"
'
'    ' Build column list and parameter placeholders
'
'    For i = 0 To lenHeaders
'        colNames = colNames & "[" & headers(i) & "], "
'        paramMarks = paramMarks & "?, "
'    Next i
'
'    ' Trim trailing commas
'    colNames = Left(colNames, Len(colNames) - 2)
'    paramMarks = Left(paramMarks, Len(paramMarks) - 2)
'
'    ' Build SQL
'    sql = "INSERT INTO [" & SheetName & "] (" & colNames & ") VALUES (" & paramMarks & ");"
''    Debug.Print sql
'
'    ' Prepare command
'    Set cmd = CreateObject("ADODB.Command")
'    Set cmd.ActiveConnection = Conn
'    cmd.CommandText = sql
'
'    ' Add parameters from array
'    For i = 0 To lenHeaders
'        cmd.Parameters.Append cmd.CreateParameter("p" & i, 200, 1, 255, CStr(vals(i)))
'    Next i
'
'    ' Execute insert
''    Debug.Print cmd.CommandText
'    On Error GoTo ErrHandler
'    cmd.Execute
'    MsgBox "The data was succuessfully written to the database.", vbInformation
'CleanExit:
'    If Conn.State = 1 Then Conn.Close: Set Conn = Nothing: Set cmd = Nothing
'    Application.EnableEvents = True
'    Exit Sub
'
'ErrHandler:
'    MsgBox Err.Number & ": " & Err.Description
'    GoTo CleanExit
    
    If Not initialized Then
        Call InitializeVariables
    End If
    Application.EnableEvents = False

    Dim SheetName As String
    Dim searchField() As Variant
    Dim searchValue() As Variant

    Dim conn As Object, cmd As Object
    Dim rs As Object
    Dim sql As String
    Dim colNames As String
    Dim paramMarks As String
    Dim vals() As Variant
'    ReDim vals(lenHeaders)
    ReDim vals(UBound(headers))
    
    If wksSheet2.Range("B3").Value = "ENTER A NEW DISTRIBUTOR" Or wksSheet2.Range("B3").Value = "SELECT A DISTRIBUTOR" Or wksSheet2.Range("B3").Value = "" Then
        MsgBox "Please select or create one from the list and try again.", vbCritical, "ERROR: You must select a customer!"
        GoTo CleanExit
    End If
    
    If wksSheet2.Range("C5").Value = "" Then
        resp = MsgBox("Would you like to continue anyways?", vbYesNo, "WARNING: Quote number field is empty!")
        If resp <> vbYes Then GoTo CleanExit
    End If
    
    If wksSheet2.Range("B54").Value = "ENTER A NEW AE" Or wksSheet2.Range("B54").Value = "SELECT AN AE" Or wksSheet2.Range("B54").Value = "" Then
        MsgBox "Please select or create one from the list and try again.", vbCritical, "ERROR: You must select a signature!"
        GoTo CleanExit
    End If
    
    'Check if record with quote number already exists
    SheetName = "Custom Confs"
    searchField = Array("Quote Number")
    searchValue = Array(wksSheet2.Range("C5").Value)

    results = Module1.SearchDatabase(SheetName, searchField, searchValue, True)
    If Not results(0, 0) = -1 Then
Selection:
        myInput = InputBox("What would like to do?" & vbCrLf & _
                 "Enter 0 to create entry with duplicate quote number." & vbCrLf & _
                 "Enter 1 to overrite existing data." & vbCrLf & _
                 "Enter 2 to review existing quote(s).", "A record with this quote number already exists.")

        Select Case myInput

        Case "0"
            GoTo DatabaseWrite
        Case "1"
'            MsgBox "This feature hasn't been implemented yet.", vbExclamation, "Please try again"
'            Dim Conn As Object, cmd As Object
'            Dim rs As Object
'            Dim sql As String
'            Dim colNames As String
'            Dim paramMarks As String
'            ReDim Preserve dataValues(0 To numFields)
'            ReDim Preserve dataFields(0 To numFields)
            
            numFields = UBound(headers)
            ReDim vals(numFields)
            SheetName = "Custom Confs"
            
            ctr = 0
            For i = 0 To UBound(dataSheetRanges)
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
            
            ' Build column list and parameter placeholders
            For i = 0 To numFields
                colNames = colNames & "[" & headers(i) & "], "
                paramMarks = paramMarks & "?, "
            Next i
            
            ' Trim trailing commas
            colNames = Left(colNames, Len(colNames) - 2)
            paramMarks = Left(paramMarks, Len(paramMarks) - 2)
        
            ' Build SQL
            sql = "UPDATE [" & SheetName & "] SET (" & colNames & ") = (" & paramMarks & ") WHERE Quote Number = " & wksSheet2.Range("C5").Value & ";"
            Debug.Print sql
        
            ' Prepare command
            Set conn = CreateObject("ADODB.Connection")
            conn.Open "Provider=Microsoft.ACE.OLEDB.12.0;" & _
                      "Data Source=" & dbPath & ";"
            Set cmd = CreateObject("ADODB.Command")
            Set cmd.ActiveConnection = conn
            cmd.CommandText = sql
            
            For i = 0 To numFields
                cmd.Parameters.Append cmd.CreateParameter("p" & i, 200, 1, 255, CStr(vals(i)))
            Next i
        
            ' Execute insert
'            Debug.Print cmd.commandText
            On Error GoTo errHandler
            cmd.Execute
            MsgBox "The data was succuessfully written to the database.", vbInformation
    
        Case "2"
            num_r = UBound(results, 2) + 1
'            results = wksSheet1.reverseResults(results)
            wksSheet1.Activate
            i = 7
            j = 16
            wksSheet1.Range("P7:Y26").ClearContents
            For r = 0 To num_r - 1
                wksSheet1.Cells(i + r, j).Value = "'" & results(0, r)
                wksSheet1.Cells(i + r, j + 1).Value = "'" & results(2, r)
                wksSheet1.Cells(i + r, j + 2).Value = "'" & results(14, r)
                wksSheet1.Cells(i + r, j + 3).Value = "'" & results(15, r)
                wksSheet1.Cells(i + r, j + 4).Value = "'" & results(6, r)
                wksSheet1.Cells(i + r, j + 5).Value = "'" & results(109, r)
                wksSheet1.Cells(i + r, j + 6).Value = "'" & results(110, r)
                wksSheet1.Cells(i + r, j + 7).Value = "'" & results(111, r)
                wksSheet1.Cells(i + r, j + 8).Value = "'" & results(188, r)
                recordDate = results(190, r)
                If Not recordDate = "" Then
                    wksSheet1.Cells(i + r, j + 9).Value = "'" & Left(recordDate, InStr(1, recordDate, " ") - 1)
                Else
                    wksSheet1.Cells(i + r, j + 9).Value = ""
                End If
            Next
            MsgBox "Found " & num_r & " matching records.", vbInformation
            wksSheet1.Range("P7").Select
            Exit Sub
        Case ""
            MsgBox "Save canceled.", vbInformation
            Exit Sub
        Case Else
            MsgBox "Please try again.", vbCritical, "Unknown command entered!"
            GoTo Selection
        End Select
    Else
DatabaseWrite:
    ' Search for existing configuration first
    numFields = UBound(headers)
    ReDim vals(numFields)
    SheetName = "Custom Confs"
    
    ctr = 0
    For i = 0 To UBound(dataSheetRanges)
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

    pumpFields = getPartialArray(headers, 12, UBound(dataSheetRanges))
    pumpVals = getPartialArray(vals, 12, UBound(dataSheetRanges))

    results = Module1.SearchDatabase(SheetName, pumpFields, pumpVals, True)
    If Not results(0, 0) = -1 Then
        ' If matching configuration is found, recover it's accompanying part number
        wksSheet1.Range("D7").Value = results(2, 0)
        vals(1) = results(2, 0)
        MsgBox "The existing part number was restored.", vbInformation, "Matching configuration found!"
    Else
        results = Module1.SearchDatabase(SheetName, Array(pumpFields(0), pumpFields(1)), Array(pumpVals(0), pumpVals(1)), True)
        If Not results(0, 0) = -1 Then
            numConfs = UBound(results, 2) + 1
            newNum = Left(wksSheet1.Range("D6").Value, 4) & "_" & Format(numConfs + 1, "000000")
            wksSheet1.Range("D7").Value = newNum
            vals(1) = newNum
        Else
            wksSheet1.Range("D7").Value = Left(wksSheet1.Range("D6").Value, 4) & "_000001"
        End If
    End If
    writeToDataBase headers, vals
    
CleanExit:
        If Not (conn Is Nothing) Then conn.Close: Set conn = Nothing
        If Not (rs Is Nothing) Then rs.Close: Set rs = Nothing
        Application.EnableEvents = True
        Exit Sub

errHandler:
        MsgBox err.Number & ": " & err.Description
        GoTo CleanExit

    End If
End Sub

Private Sub Worksheet_Change(ByVal Target As Range)
    Call InitializeVariables
    'Handle new distributor entry
    If Target.Row = 3 And Target.Column = 2 Then
        If Target.Value = "ENTER A NEW DISTRIBUTOR" Then
            newDistributor = InputBox("Please enter the name of the new distributor below.")
            If newDistributor = "" Then
                Cells(3, 2).Value = "SELECT A DISTRIBUTOR"
            Else
                Cells(3, 2).Value = newDistributor
            End If
        End If
    End If
   
    'Handle new AE entry
    If Target.Row = 54 And Target.Column = 2 Then
        If Target.Value = "ENTER A NEW AE" Then
            newAE = InputBox("Please enter the name of the new engineer below.")
            If newAE = "" Then
                Cells(54, 2).Value = "SELECT AN AE"
            Else
                Cells(54, 2).Value = newAE
            End If
        End If
    End If
End Sub
