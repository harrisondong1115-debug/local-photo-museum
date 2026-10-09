#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "Styling/SlateBrush.h"
#include "MuseumRuntime.generated.h"

class UCameraComponent;
class UTexture2D;
class SWidget;

struct FMuseumPhoto
{
    FString Id, Name, File;
};
struct FMuseumAlbum
{
    FString Id, Title;
    TArray<FMuseumPhoto> Photos;
};

UCLASS()
class MOMENTMUSEUM_API AMuseumCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    AMuseumCharacter();
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
};

UCLASS()
class MOMENTMUSEUM_API AMuseumGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AMuseumGameMode();
};

UCLASS()
class MOMENTMUSEUM_API AMuseumController : public APlayerController
{
    GENERATED_BODY()
public:
    AMuseumController();
    virtual void BeginPlay() override;
    virtual void SetupInputComponent() override;
    virtual bool InputKey(const FInputKeyEventArgs& Params) override;
    virtual void PlayerTick(float DeltaTime) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
    TArray<FMuseumAlbum> Albums;
    FString CollectionRoot;
    int32 AlbumIndex = INDEX_NONE, PhotoIndex = 0, RequestGeneration = 0;
    bool bGallery = false, bDragging = false, bFast = false, bHighQuality = false;
    bool bSlatePointerDragging = false;
    FVector2D LastMouse = FVector2D::ZeroVector;
    float DragDistance = 0;
    double LastFrameLog = 0;
    TArray<float> FrameTimes;
    bool bMuseumQA = false, bQAInitialised = false, bQARayPick = false;
    float QATime = 0;
    int32 QAStep = 0;
    FRotator QARotation;
    FString QADirectory;
    TArray<float> QAMovingFrameTimes;
    TSharedPtr<SWidget> GalleryWidget, HintWidget, InputSurface;
    TSharedPtr<FSlateBrush> PhotoBrush;
    UPROPERTY(Transient) TObjectPtr<UTexture2D> CurrentPhoto;

    void Forward(float Value);
    void Right(float Value);
    void DragStart();
    void DragEnd();
    void LookStart();
    void LookEnd();
    void OpenCatalogue();
    void CloseGallery();
    void PreviousPhoto();
    void NextPhoto();
    void GoEntry();
    void GoGarden();
    void FastStart();
    void FastEnd();
    void ToggleQuality();
    void ToggleStats();
    void TeleportToTag(FName Tag);
    void LoadCatalogue();
    void OpenAlbum(int32 Album, int32 Photo = 0);
    void RebuildGallery();
    void RequestPhoto();
    void ApplyPhoto(int32 Generation, int32 Width, int32 Height, TArray64<uint8>&& Pixels);
    void RemoveGalleryWidget();
    bool OpenExhibit(AActor* Actor);
    void RunMuseumQA(float DeltaTime);
};
