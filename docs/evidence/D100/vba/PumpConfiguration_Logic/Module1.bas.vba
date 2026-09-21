Attribute VB_Name = "Module1"
Sub createTable()

    Dim currLine As String
    
    Set wksSheet = ThisWorkbook.Worksheets("Pump Options")
    For r = 4 To 209
        currSeries = wksSheet.Cells(r, 2)
        If currSeries = currLine
        prodLine = ""
        For i = 1 To Len(Series)
            char = Mid(Series, i, 1)
            If Not (char Like "[A-Z]") Then
                Exit For
            Else
                prodLine = prodLine & char
            End If
        Next
    Next
   
   firstCol = wksSheet.Cells(230, Columns.Count).End(xlToLeft).Column
'   Debug.Print firstCol

End Sub
