using UnrealBuildTool;
public class MomentMuseumTarget : TargetRules
{
    public MomentMuseumTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("MomentMuseum");
    }
}
