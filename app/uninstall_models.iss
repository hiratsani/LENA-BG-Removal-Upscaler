; Optional model cleanup. Never follows directory junctions or symbolic links.
[Code]
var
  RemoveDownloadedModels: Boolean;

function GetFileAttributes(const FileName: String): Integer;
  external 'GetFileAttributesW@kernel32.dll stdcall';

function ModelCacheRoot: String;
begin
#ifdef LENA_UNINSTALL_TEST_ROOT
  Result := ExpandFileName('{#LENA_UNINSTALL_TEST_ROOT}');
#else
  Result := ExpandConstant('{localappdata}\LENA\models');
#endif
end;

function SafeModelPath(const Path: String): Boolean;
var Root, Candidate: String;
begin
  Root := AddBackslash(ExpandFileName(ModelCacheRoot));
  Candidate := AddBackslash(ExpandFileName(Path));
  Result := CompareText(Copy(Candidate, 1, Length(Root)), Root) = 0;
end;

function PlainModelDirectory(const Path: String): Boolean;
var Attributes: Integer;
begin
  Result := False;
  if not SafeModelPath(Path) then exit;
  Attributes := GetFileAttributes(Path);
  if Attributes = -1 then exit;
  Result := ((Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0) and
            ((Attributes and FILE_ATTRIBUTE_REPARSE_POINT) = 0);
end;

function ModelFolderBytes(const Path: String): Int64;
var Entry: TFindRec;
begin
  Result := 0;
  if not PlainModelDirectory(Path) then exit;
  if FindFirst(AddBackslash(Path) + '*', Entry) then begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') and
           ((Entry.Attributes and FILE_ATTRIBUTE_REPARSE_POINT) = 0) then begin
          if (Entry.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            Result := Result + ModelFolderBytes(AddBackslash(Path) + Entry.Name)
          else
            Result := Result + (Int64(Entry.SizeHigh) * 4294967296) + Entry.SizeLow;
        end;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
end;

function RemoveModelFolder(const Path: String): Boolean;
var Entry: TFindRec; Child: String;
begin
  Result := False;
  if not PlainModelDirectory(Path) then exit;
  Result := True;
  if FindFirst(AddBackslash(Path) + '*', Entry) then begin
    try
      repeat
        if (Entry.Name <> '.') and (Entry.Name <> '..') then begin
          Child := AddBackslash(Path) + Entry.Name;
          if (Entry.Attributes and FILE_ATTRIBUTE_REPARSE_POINT) <> 0 then
            Result := False
          else if (Entry.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then begin
            if not RemoveModelFolder(Child) then Result := False;
          end else if not DeleteFile(Child) then Result := False;
        end;
      until not FindNext(Entry);
    finally
      FindClose(Entry);
    end;
  end;
  if not RemoveDir(Path) then Result := False;
end;

function UninstallIndonesian: Boolean;
var Settings: AnsiString; Text: String;
begin
  Result := True;
  if LoadStringFromFile(ExpandConstant('{localappdata}\LENA\settings.json'), Settings) then begin
    Text := String(Settings);
    StringChangeEx(Text, ' ', '', True);
    Result := Pos('"language":"en"', Text) = 0;
  end;
end;

function UninstallWords(const Indonesian, English: String): String;
begin
  if UninstallIndonesian then Result := Indonesian else Result := English;
end;

function ModelSizeLabel(Bytes: Int64): String;
begin
  if Bytes >= 1000000000 then Result := Format('%.2f GB', [Bytes / 1000000000.0])
  else if Bytes >= 1000000 then Result := Format('%.1f MB', [Bytes / 1000000.0])
  else if Bytes >= 1000 then Result := Format('%.1f KB', [Bytes / 1000.0])
  else Result := IntToStr(Bytes) + ' bytes';
end;

function ShowModelRemovalChoice: Boolean;
var
  Form: TSetupForm;
  Intro, Details, Folder: TNewStaticText;
  Choice: TNewCheckBox;
  ContinueButton, CancelButton: TNewButton;
begin
  RemoveDownloadedModels := False;
  Result := True;
  if not DirExists(ModelCacheRoot) then exit;
#if VER >= EncodeVer(6, 6, 0)
  Form := CreateCustomForm(ScaleX(450), ScaleY(260), False, False);
#else
  Form := CreateCustomForm;
  Form.ClientWidth := ScaleX(450);
  Form.ClientHeight := ScaleY(260);
#endif
  try
    Form.Caption := UninstallWords('Hapus LENA', 'Uninstall LENA');
    Form.BorderStyle := bsDialog;
    Form.Constraints.MinWidth := 0;
    Form.Constraints.MinHeight := 0;
    Form.Width := ScaleX(450) + (Form.Width - Form.ClientWidth);
    Form.Height := ScaleY(260) + (Form.Height - Form.ClientHeight);
    Form.Constraints.MaxWidth := Form.Width;
    Form.Constraints.MinWidth := Form.Width;
    Form.Constraints.MaxHeight := Form.Height;
    Form.Constraints.MinHeight := Form.Height;
    Form.Position := poScreenCenter;
    Intro := TNewStaticText.Create(Form);
    Intro.Parent := Form;
    Intro.SetBounds(ScaleX(22), ScaleY(20), ScaleX(406), ScaleY(42));
    Intro.AutoSize := False; Intro.WordWrap := True;
    Intro.Caption := UninstallWords('Simpan model untuk dipakai lagi, atau hapus untuk mengosongkan ruang.',
      'Keep downloaded models for later, or remove them to free up space.');
    Choice := TNewCheckBox.Create(Form);
    Choice.Parent := Form;
    Choice.SetBounds(ScaleX(22), ScaleY(76), ScaleX(406), ScaleY(24));
    Choice.Caption := UninstallWords('Hapus juga model yang di-download', 'Also remove downloaded models') +
      ' (' + ModelSizeLabel(ModelFolderBytes(ModelCacheRoot)) + ')';
    Choice.Checked := False;
    Choice.Enabled := PlainModelDirectory(ModelCacheRoot);
    Details := TNewStaticText.Create(Form);
    Details.Parent := Form; Details.AutoSize := False; Details.WordWrap := True;
    Details.SetBounds(ScaleX(22), ScaleY(112), ScaleX(406), ScaleY(40));
    Details.Caption := UninstallWords('Jika dihapus, model tambahan perlu di-download lagi saat LENA dipasang ulang. Foto dan hasil export tetap disimpan.',
      'If removed, optional models will need to be downloaded again after reinstalling LENA. Your photos and exports are kept.');
    Folder := TNewStaticText.Create(Form);
    Folder.Parent := Form; Folder.AutoSize := False; Folder.WordWrap := True;
    Folder.SetBounds(ScaleX(22), ScaleY(164), ScaleX(406), ScaleY(40));
    Folder.Caption := ModelCacheRoot;
    ContinueButton := TNewButton.Create(Form); ContinueButton.Parent := Form;
    ContinueButton.SetBounds(ScaleX(246), ScaleY(222), ScaleX(88), ScaleY(26));
    ContinueButton.Caption := UninstallWords('Lanjut', 'Continue');
    ContinueButton.ModalResult := mrOk; ContinueButton.Default := True;
    CancelButton := TNewButton.Create(Form); CancelButton.Parent := Form;
    CancelButton.SetBounds(ScaleX(342), ScaleY(222), ScaleX(88), ScaleY(26));
    CancelButton.Caption := UninstallWords('Batal', 'Cancel');
    CancelButton.ModalResult := mrCancel; CancelButton.Cancel := True;
    Result := Form.ShowModal = mrOk;
    if Result then RemoveDownloadedModels := Choice.Checked and Choice.Enabled;
  finally
    Form.Free;
  end;
end;

function InitializeUninstall: Boolean;
begin
  RemoveDownloadedModels := False;
  Result := True;
  if not UninstallSilent then Result := ShowModelRemovalChoice;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    // Shortcut cleanup is also best-effort. Ignore permission failures.
    DeleteFile(ExpandConstant('{group}\LENA.lnk'));
    DeleteFile(ExpandConstant('{userdesktop}\LENA.lnk'));
    RemoveDir(ExpandConstant('{group}'));

    if RemoveDownloadedModels then begin
      if not RemoveModelFolder(ModelCacheRoot) then
        MsgBox(UninstallWords('Sebagian file model tidak bisa dihapus. Kamu bisa memeriksa folder berikut:',
          'Some model files could not be removed. You can check the following folder:') + #13#10 + ModelCacheRoot,
          mbInformation, MB_OK);
    end;
  end;
end;
