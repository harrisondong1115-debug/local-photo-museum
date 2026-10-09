using UnrealBuildTool;
public class MomentMuseum : ModuleRules
{
    public MomentMuseum(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new string[] {
            "Core", "CoreUObject", "Engine", "InputCore", "Slate", "SlateCore",
            "Json", "JsonUtilities", "ImageWrapper", "RenderCore", "RHI"
        });
    }
}
