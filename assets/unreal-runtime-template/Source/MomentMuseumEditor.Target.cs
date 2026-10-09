using UnrealBuildTool;
public class MomentMuseumEditorTarget : TargetRules
{
    public MomentMuseumEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("MomentMuseum");
    }
}
