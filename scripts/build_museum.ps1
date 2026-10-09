param(
    [Parameter(Mandatory=$true)][string]$EngineRoot,
    [Parameter(Mandatory=$true)][string]$Project,
    [Parameter(Mandatory=$true)][string]$CacheRoot,
    [switch]$SkipEditorBuild,
    [switch]$Package,
    [string]$ArchiveDirectory
)
$ErrorActionPreference='Stop'
$enginePath=(Resolve-Path -LiteralPath $EngineRoot).Path
$projectPath=(Resolve-Path -LiteralPath $Project).Path
$projectFolder=Split-Path -Parent $projectPath
$migration=Join-Path (Split-Path -Parent $projectFolder) 'Migration'
$editor=Join-Path $enginePath 'Engine\Binaries\Win64\UnrealEditor-Cmd.exe'
$build=Join-Path $enginePath 'Engine\Build\BatchFiles\Build.bat'
$uat=Join-Path $enginePath 'Engine\Build\BatchFiles\RunUAT.bat'
$script=Join-Path $projectFolder 'Tools\import_museum.py'
foreach($required in @($editor,$build,$script,(Join-Path $migration 'scene.json'),(Join-Path $migration 'scene_settings.json'),(Join-Path $projectFolder 'Content\Collections\catalogue.json'))) {
    if(!(Test-Path -LiteralPath $required -PathType Leaf)) { throw "Required input missing: $required" }
}
if($Package -and [string]::IsNullOrWhiteSpace($ArchiveDirectory)) { throw 'Pass -ArchiveDirectory with -Package.' }
$cachePath=[IO.Path]::GetFullPath($CacheRoot)
New-Item -ItemType Directory -Force -Path $cachePath | Out-Null
Set-Item -LiteralPath 'Env:UE-LocalDataCachePath' -Value (Join-Path $cachePath 'DDC')
Set-Item -LiteralPath 'Env:UE-ZenDataPath' -Value (Join-Path $cachePath 'Zen')
Set-Item -LiteralPath 'Env:UE-SharedDataCachePath' -Value 'None'
$logs=Join-Path $projectFolder 'Saved\SkillBuildLogs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
if(!$SkipEditorBuild) {
    & $build MomentMuseumEditor Win64 Development "-Project=$projectPath" -WaitMutex -NoHotReloadFromIDE -UTF8Output *>&1 | Out-File (Join-Path $logs 'EditorBuild.log') -Encoding utf8
    if($LASTEXITCODE -ne 0) { throw 'Editor build failed; inspect EditorBuild.log.' }
}
$importLog=Join-Path $logs 'SceneImport.log'
& $editor $projectPath "-ExecutePythonScript=$script" -nullrhi -unattended -nosplash -NoSound -UTF8Output -stdout *>&1 | Out-File $importLog -Encoding utf8
if($LASTEXITCODE -ne 0 -or (Select-String -LiteralPath $importLog -Pattern 'LogPython: Error' -Quiet)) { throw 'Scene import failed; inspect SceneImport.log.' }
if(!(Test-Path -LiteralPath (Join-Path $projectFolder 'Content\Museum\Museum.umap'))) { throw 'Museum.umap was not created.' }
if($Package) {
    $archivePath=[IO.Path]::GetFullPath($ArchiveDirectory)
    & $uat BuildCookRun "-project=$projectPath" -noP4 -platform=Win64 -clientconfig=Development -build -nocompileeditor -cook -stage -pak -iostore -archive "-stagingdirectory=$(Join-Path $cachePath 'StagedBuilds')" "-archivedirectory=$archivePath" -utf8output *>&1 | Out-File (Join-Path $logs 'PackageBuild.log') -Encoding utf8
    if($LASTEXITCODE -ne 0) { throw 'Packaging failed; inspect PackageBuild.log.' }
}
Write-Output 'Build steps completed. Native motion, pointer interactions and frame times still need testing.'
