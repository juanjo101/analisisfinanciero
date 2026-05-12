; Script de Inno Setup para Análisis Financiero
; Este script crea un instalador profesional (Wizard) que pregunta por la ruta de instalación.

[Setup]
AppId={{A9B8C7D6-E5F4-4321-B0A1-C2D3E4F5A6B7}
AppName=Análisis Financiero
AppVersion=1.0
AppPublisher=Juanjo Diaz
DefaultDirName={autopf}\AnalisisFinanciero
DefaultGroupName=Análisis Financiero
AllowNoIcons=yes
SetupIconFile=app_icon.ico
; Carpeta donde se guardará el instalador final
OutputDir=.
OutputBaseFilename=Instalador_Financiero_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; IMPORTANTE: Asegúrate de que el .exe ya esté generado en la carpeta dist antes de compilar este script
Source: "dist\AnalisisFinanciero.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; Si necesitas incluir carpetas adicionales que no estén en el .exe:
; Source: "PlantillaBC_2Grupo No. 1.xlsx"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Análisis Financiero"; Filename: "{app}\AnalisisFinanciero.exe"
Name: "{autodesktop}\Análisis Financiero"; Filename: "{app}\AnalisisFinanciero.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AnalisisFinanciero.exe"; Description: "{cm:LaunchProgram,Análisis Financiero}"; Flags: nowait postinstall skipifsilent
