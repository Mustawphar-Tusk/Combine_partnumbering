Attribute VB_Name = "Module3"
Sub TestSQLConnection()

    Dim conn As Object
    Set conn = CreateObject("ADODB.Connection")

    conn.Open "Provider=SQLOLEDB;" & _
              "Data Source=localhost;" & _
              "Initial Catalog=PumpConfiguratorDB;" & _
              "Integrated Security=SSPI;"

    MsgBox "Connected to SQL Server successfully!"

    conn.Close
    Set conn = Nothing

End Sub


