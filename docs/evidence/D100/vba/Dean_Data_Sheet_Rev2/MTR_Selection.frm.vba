Attribute VB_Name = "MTR_Selection"
Attribute VB_Base = "0{6B73A187-60F0-4284-A2F9-F215A4A4B14E}{040FB39F-38CF-48D5-9865-5A60D16C7B89}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Private m_Cancelled As Boolean
Private m_Selections As Variant

Private Sub CancelButton_Click()
    Hide
    m_Cancelled = True
End Sub

Private Sub ConfirmButton_Click()
    If CheckBox_Casing.Value = True Then m_Selections = m_Selections & "Casing, "
    If CheckBox_Impeller.Value = True Then m_Selections = m_Selections & "Impeller, "
    If CheckBox_Backhead.Value = True Then m_Selections = m_Selections & "Backhead, "
    If CheckBox_Shaft.Value = True Then m_Selections = m_Selections & "Shaft, "
    If CheckBox_Sleeve.Value = True Then m_Selections = m_Selections & "Sleeve, "
    If Len(m_Selections) > 0 Then m_Selections = Left(m_Selections, Len(m_Selections) - 2)
    Hide
End Sub

Private Sub UserForm_Initialize()
    m_Selections = ""
End Sub

Public Property Get Selections() As String
    Selections = m_Selections
End Property

Public Property Get Cancelled() As Boolean
    Cancelled = m_Cancelled
End Property

Private Sub UserForm_QueryClose(Cancel As Integer, CloseMode As Integer)
    If CloseMode = vbFormControlMenu Then Cancel = True
    Hide
    m_Cancelled = True
End Sub
