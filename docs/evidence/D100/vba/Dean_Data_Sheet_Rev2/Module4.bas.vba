Attribute VB_Name = "Module4"
Sub GeneratePartNumber()

    Dim conn As Object
    Dim cmd As Object
    Dim rs As Object
    Dim configId As Long
    Dim partNumber As String

    configId = Sheet1.Range("B2").Value

    Set conn = CreateObject("ADODB.Connection")
    conn.Open "Provider=SQLOLEDB;" & _
              "Data Source=localhost;" & _
              "Initial Catalog=PumpConfiguratorDB;" & _
              "Integrated Security=SSPI;"

    Set cmd = CreateObject("ADODB.Command")
    Set cmd.ActiveConnection = conn
    cmd.CommandType = 4
    cmd.CommandText = "sp_GeneratePartNumber"

    cmd.Parameters.Append cmd.CreateParameter("@config_id", 3, 1, , configId)
    cmd.Parameters.Append cmd.CreateParameter("@part_number", 202, 2, 200)

    cmd.Execute

    partNumber = cmd.Parameters("@part_number").Value

    Sheet1.Range("B5").Value = partNumber

    conn.Close

    Set cmd = Nothing
    Set conn = Nothing

    MsgBox "Part Number Generated: " & partNumber

End Sub

