#include "MuseumRuntime.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/Texture2D.h"
#include "EngineUtils.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/IConsoleManager.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "IImageWrapper.h"
#include "IImageWrapperModule.h"
#include "Modules/ModuleManager.h"
#include "Async/Async.h"
#include "Widgets/SOverlay.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Text/STextBlock.h"
#include "Framework/Application/SlateApplication.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/EngineVersion.h"
#include "HAL/FileManager.h"
#include "Engine/GameViewportClient.h"
#include "UnrealClient.h"
#include "RHI.h"
#include "InputKeyEventArgs.h"
#include "Styling/CoreStyle.h"

DEFINE_LOG_CATEGORY_STATIC(LogMomentMuseum, Log, All);

AMuseumCharacter::AMuseumCharacter()
{
    GetCapsuleComponent()->InitCapsuleSize(30, 88);
    GetCharacterMovement()->MaxWalkSpeed = 260;
    GetCharacterMovement()->BrakingDecelerationWalking = 1800;
    GetCharacterMovement()->MaxStepHeight = 35;
    bUseControllerRotationYaw = true;
    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("MuseumCamera"));
    Camera->SetupAttachment(GetCapsuleComponent());
    Camera->SetRelativeLocation(FVector(0,0,75));
    Camera->bUsePawnControlRotation = true;
    Camera->FieldOfView = 85;
}

AMuseumGameMode::AMuseumGameMode()
{
    DefaultPawnClass = AMuseumCharacter::StaticClass();
    PlayerControllerClass = AMuseumController::StaticClass();
}

AMuseumController::AMuseumController()
{
    bShowMouseCursor = true;
    PrimaryActorTick.bCanEverTick = true;
}

void AMuseumController::BeginPlay()
{
    Super::BeginPlay();
    CollectionRoot = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Collections"));
    LoadCatalogue();
    bMuseumQA=FParse::Param(FCommandLine::Get(),TEXT("MuseumQA"));
    if(bMuseumQA)
    {
        QADirectory=FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("MuseumQA")));
        IFileManager::Get().MakeDirectory(*QADirectory,true);
        if(FParse::Param(FCommandLine::Get(),TEXT("MuseumQAQuality")))
        {
            QADirectory+=TEXT("Quality");
            IFileManager::Get().MakeDirectory(*QADirectory,true);
            ToggleQuality();
        }
    }
    PhotoBrush = MakeShared<FSlateBrush>();
    PhotoBrush->DrawAs = ESlateBrushDrawType::Image;
    SetInputMode(FInputModeGameAndUI().SetHideCursorDuringCapture(false));
    if(GEngine && GEngine->GameViewport) GEngine->GameViewport->SetMouseCaptureMode(EMouseCaptureMode::NoCapture);
    if (GEngine && GEngine->GameViewport)
    {
        TWeakObjectPtr<AMuseumController> Weak(this);
        auto MovePointer=[Weak](const FPointerEvent& Event)
        {
            if(!Weak.IsValid() || !Weak->bSlatePointerDragging) return;
            FVector2D Position=Event.GetScreenSpacePosition();
            FVector2D Delta=Position-Weak->LastMouse;
            Weak->LastMouse=Position;
            Weak->DragDistance+=Delta.Size();
            FRotator Rotation=Weak->GetControlRotation();
            Rotation.Yaw+=Delta.X*0.18f;
            Rotation.Pitch=FMath::Clamp(FRotator::NormalizeAxis(Rotation.Pitch)-Delta.Y*0.12f,-65.f,65.f);
            Weak->SetControlRotation(Rotation);
        };
        auto PointerDown=[Weak](const FGeometry&,const FPointerEvent& Event)
        {
            if(!Weak.IsValid() || Weak->bGallery || (Event.GetEffectingButton()!=EKeys::LeftMouseButton && Event.GetEffectingButton()!=EKeys::RightMouseButton)) return FReply::Unhandled();
            Weak->LastMouse=Event.GetScreenSpacePosition();
            Weak->DragDistance=Event.GetEffectingButton()==EKeys::RightMouseButton?100:0;
            Weak->bSlatePointerDragging=true;
            return FReply::Handled().CaptureMouse(Weak->InputSurface.ToSharedRef());
        };
        SAssignNew(InputSurface,SBorder).Padding(0)
          .BorderImage(FCoreStyle::Get().GetBrush(TEXT("NoBrush")))
          .OnMouseButtonDown_Lambda(PointerDown)
          .OnMouseDoubleClick_Lambda(PointerDown)
          .OnMouseMove_Lambda([Weak,MovePointer](const FGeometry&,const FPointerEvent& Event)
          { MovePointer(Event); return Weak.IsValid() && Weak->bSlatePointerDragging?FReply::Handled():FReply::Unhandled(); })
          .OnMouseButtonUp_Lambda([Weak,MovePointer](const FGeometry& Geometry,const FPointerEvent& Event)
          {
              if(!Weak.IsValid() || !Weak->bSlatePointerDragging) return FReply::Unhandled();
              MovePointer(Event); Weak->bSlatePointerDragging=false;
              UE_LOG(LogMomentMuseum,Display,TEXT("Pointer drag distance=%.2f rotation=%s"),Weak->DragDistance,*Weak->GetControlRotation().ToString());
              if(Event.GetEffectingButton()==EKeys::LeftMouseButton && Weak->DragDistance<6 && !Weak->bGallery)
              {
                  const FVector2D Local=Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition());
                  const FVector2D Size=Geometry.GetLocalSize();
                  const FIntPoint Pixels=GEngine->GameViewport->Viewport->GetSizeXY();
                  FVector Origin,Direction;
                  if(Size.X>0 && Size.Y>0 && Weak->DeprojectScreenPositionToWorld(Local.X*Pixels.X/Size.X,Local.Y*Pixels.Y/Size.Y,Origin,Direction))
                  {
                      FHitResult Hit;
                      if(Weak->GetWorld()->LineTraceSingleByChannel(Hit,Origin,Origin+Direction*100000,ECC_Visibility,FCollisionQueryParams(TEXT("PointerPick"),true,Weak->GetPawn()))) Weak->OpenExhibit(Hit.GetActor());
                  }
              }
              return FReply::Handled().ReleaseMouseCapture();
          });
        GEngine->GameViewport->AddViewportWidgetContent(InputSurface.ToSharedRef(),0);
        SAssignNew(HintWidget, SOverlay)
        + SOverlay::Slot().HAlign(HAlign_Center).VAlign(VAlign_Bottom).Padding(12)
        [ SNew(SBorder).Padding(12).BorderBackgroundColor(FLinearColor(0.02f,0.03f,0.04f,0.72f))
          [ SNew(STextBlock).ColorAndOpacity(FLinearColor(0.85f,0.88f,0.90f))
            .Text(FText::FromString(TEXT("WASD 移动 · 拖动转头 · 点照片打开合集 · Tab 全部合集 · O 庭院 · Home 入口 · F8 画质 · F9 帧率"))) ] ];
        GEngine->GameViewport->AddViewportWidgetContent(HintWidget.ToSharedRef(), 1);
    }
    UE_LOG(LogMomentMuseum, Display, TEXT("Museum ready. Local albums=%d, HWRT Lumen + TSR, no path tracer."), Albums.Num());
}

void AMuseumController::SetupInputComponent()
{
    Super::SetupInputComponent();
    InputComponent->BindAxis(TEXT("Forward"),this,&AMuseumController::Forward);
    InputComponent->BindAxis(TEXT("Right"),this,&AMuseumController::Right);
    InputComponent->BindAction(TEXT("Catalogue"),IE_Pressed,this,&AMuseumController::OpenCatalogue);
    InputComponent->BindAction(TEXT("Close"),IE_Pressed,this,&AMuseumController::CloseGallery);
    InputComponent->BindAction(TEXT("Previous"),IE_Pressed,this,&AMuseumController::PreviousPhoto);
    InputComponent->BindAction(TEXT("Next"),IE_Pressed,this,&AMuseumController::NextPhoto);
    InputComponent->BindAction(TEXT("Entry"),IE_Pressed,this,&AMuseumController::GoEntry);
    InputComponent->BindAction(TEXT("Garden"),IE_Pressed,this,&AMuseumController::GoGarden);
    InputComponent->BindAction(TEXT("Fast"),IE_Pressed,this,&AMuseumController::FastStart);
    InputComponent->BindAction(TEXT("Fast"),IE_Released,this,&AMuseumController::FastEnd);
    InputComponent->BindAction(TEXT("Quality"),IE_Pressed,this,&AMuseumController::ToggleQuality);
    InputComponent->BindAction(TEXT("Stats"),IE_Pressed,this,&AMuseumController::ToggleStats);
}

void AMuseumController::Forward(float Value)
{
    if (!bGallery && GetPawn() && Value != 0)
        GetPawn()->AddMovementInput(FRotationMatrix(FRotator(0,GetControlRotation().Yaw,0)).GetUnitAxis(EAxis::X),Value);
}
bool AMuseumController::InputKey(const FInputKeyEventArgs& Params)
{
    // Process mouse edges immediately. A fast drag can begin and end between
    // two game ticks; deferred action bindings would lose its entire distance.
    if(!bGallery && (Params.Key==EKeys::LeftMouseButton || Params.Key==EKeys::RightMouseButton))
    {
        if(Params.Event==IE_Pressed)
        {
            if(Params.Key==EKeys::RightMouseButton) LookStart(); else DragStart();
        }
        else if(Params.Event==IE_Released) DragEnd();
        return true;
    }
    return Super::InputKey(Params);
}
void AMuseumController::Right(float Value)
{
    if (!bGallery && GetPawn() && Value != 0)
        GetPawn()->AddMovementInput(FRotationMatrix(FRotator(0,GetControlRotation().Yaw,0)).GetUnitAxis(EAxis::Y),Value);
}
void AMuseumController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    if(bMuseumQA) RunMuseumQA(DeltaTime);
    if (bDragging && !bGallery && !bSlatePointerDragging)
    {
        float DX=0,DY=0; GetInputMouseDelta(DX,DY);
        float X,Y;
        if (GetMousePosition(X,Y))
        {
            FVector2D Pos(X,Y), Delta = Pos-LastMouse;
            if(!FMath::IsNearlyZero(DX) || !FMath::IsNearlyZero(DY)) Delta=FVector2D(DX,-DY);
            LastMouse=Pos;
            DragDistance += Delta.Size();
            FRotator Rotation=GetControlRotation();
            // User-approved direction: dragging right looks right.
            Rotation.Yaw += Delta.X*0.18f;
            Rotation.Pitch = FMath::Clamp(FRotator::NormalizeAxis(Rotation.Pitch)-Delta.Y*0.12f,-65.f,65.f);
            Rotation.Roll=0;
            SetControlRotation(Rotation);
        }
    }
    if (!bGallery && DeltaTime > 0)
    {
        FrameTimes.Add(DeltaTime*1000);
        if (FPlatformTime::Seconds()-LastFrameLog>10 && FrameTimes.Num()>60)
        {
            FrameTimes.Sort();
            float Sum=0;
            for(float T:FrameTimes) Sum+=T;
            const int32 Index=FMath::Clamp(FMath::FloorToInt(FrameTimes.Num()*0.99f),0,FrameTimes.Num()-1);
            UE_LOG(LogMomentMuseum,Display,TEXT("FrameStats frames=%d meanMs=%.2f p99Ms=%.2f preset=%s"),
                FrameTimes.Num(),Sum/FrameTimes.Num(),FrameTimes[Index],bHighQuality?TEXT("Quality"):TEXT("Balanced"));
            FrameTimes.Reset(); LastFrameLog=FPlatformTime::Seconds();
        }
    }
}

void AMuseumController::DragStart()
{
    if(bGallery) return;
    float X=0,Y=0; GetMousePosition(X,Y);
    LastMouse=FVector2D(X,Y); DragDistance=0; bDragging=true;
}
void AMuseumController::LookStart(){ DragStart(); DragDistance=100; }
void AMuseumController::LookEnd(){ bDragging=false; }
void AMuseumController::DragEnd()
{
    if(bDragging && !bGallery)
    {
        float DX=0,DY=0; GetInputMouseDelta(DX,DY);
        if(FMath::IsNearlyZero(DX) && FMath::IsNearlyZero(DY))
        {
            float X=0,Y=0;
            if(GetMousePosition(X,Y)){ DX=X-LastMouse.X; DY=LastMouse.Y-Y; }
        }
        DragDistance+=FVector2D(DX,DY).Size();
        FRotator Rotation=GetControlRotation();
        Rotation.Yaw+=DX*0.18f;
        Rotation.Pitch=FMath::Clamp(FRotator::NormalizeAxis(Rotation.Pitch)+DY*0.12f,-65.f,65.f);
        SetControlRotation(Rotation);
    }
    UE_LOG(LogMomentMuseum,Display,TEXT("Mouse drag distance=%.2f rotation=%s"),DragDistance,*GetControlRotation().ToString());
    const bool bClick=bDragging && DragDistance<6;
    bDragging=false;
    if(!bClick || bGallery) return;
    FHitResult Hit;
    if(GetHitResultUnderCursor(ECC_Visibility,true,Hit) && Hit.GetActor())
    {
        OpenExhibit(Hit.GetActor());
    }
}
bool AMuseumController::OpenExhibit(AActor* Actor)
{
    if(!Actor) return false;
        FString AlbumId,PhotoId;
        for(FName Tag:Actor->Tags)
        {
            FString Value=Tag.ToString();
            if(Value.StartsWith(TEXT("Album="))) AlbumId=Value.Mid(6);
            if(Value.StartsWith(TEXT("Photo="))) PhotoId=Value.Mid(6);
        }
        for(int32 I=0;I<Albums.Num();++I)
        {
            if(Albums[I].Id==AlbumId)
            {
                int32 P=Albums[I].Photos.IndexOfByPredicate([&](const FMuseumPhoto& Photo){ return Photo.Id==PhotoId; });
                OpenAlbum(I,FMath::Max(P,0)); return true;
            }
        }
    return false;
}

void AMuseumController::LoadCatalogue()
{
    FString Json;
    if(!FFileHelper::LoadFileToString(Json,*FPaths::Combine(CollectionRoot,TEXT("catalogue.json"))))
    { UE_LOG(LogMomentMuseum,Error,TEXT("Missing local catalogue")); return; }
    TSharedPtr<FJsonObject> Root;
    if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Root) || !Root) return;
    const TArray<TSharedPtr<FJsonValue>>* Rows=nullptr;
    if(!Root->TryGetArrayField(TEXT("albums"),Rows)) return;
    for(const auto& Row:*Rows)
    {
        auto Obj=Row->AsObject(); if(!Obj) continue;
        FMuseumAlbum Album;
        Obj->TryGetStringField(TEXT("id"),Album.Id);
        Obj->TryGetStringField(TEXT("title"),Album.Title);
        const TArray<TSharedPtr<FJsonValue>>* Photos=nullptr;
        if(Obj->TryGetArrayField(TEXT("photos"),Photos))
        {
            for(const auto& Value:*Photos)
            {
                auto P=Value->AsObject(); if(!P) continue;
                FMuseumPhoto Photo;
                P->TryGetStringField(TEXT("id"),Photo.Id);
                P->TryGetStringField(TEXT("name"),Photo.Name);
                Photo.File=FPaths::Combine(CollectionRoot,TEXT("Photos"),Photo.Id+TEXT(".jpg"));
                if(FPaths::FileExists(Photo.File)) Album.Photos.Add(MoveTemp(Photo));
            }
        }
        if(Album.Photos.Num()>0) Albums.Add(MoveTemp(Album));
    }
}

void AMuseumController::OpenCatalogue()
{
    if(bGallery){ CloseGallery(); return; }
    AlbumIndex=INDEX_NONE; bGallery=true; bDragging=false;
    RebuildGallery();
}
void AMuseumController::OpenAlbum(int32 Album,int32 Photo)
{
    if(!Albums.IsValidIndex(Album) || Albums[Album].Photos.IsEmpty()) return;
    AlbumIndex=Album; PhotoIndex=FMath::Clamp(Photo,0,Albums[Album].Photos.Num()-1);
    bGallery=true; bDragging=false;
    RequestPhoto(); RebuildGallery();
}
void AMuseumController::RemoveGalleryWidget()
{
    if(GalleryWidget.IsValid() && GEngine && GEngine->GameViewport)
        GEngine->GameViewport->RemoveViewportWidgetContent(GalleryWidget.ToSharedRef());
    GalleryWidget.Reset();
}
void AMuseumController::CloseGallery()
{
    if(!bGallery) return;
    ++RequestGeneration; bGallery=false;
    RemoveGalleryWidget();
    if(PhotoBrush) PhotoBrush->SetResourceObject(nullptr);
    CurrentPhoto=nullptr;
    FSlateApplication::Get().SetAllUserFocusToGameViewport();
    SetInputMode(FInputModeGameAndUI().SetHideCursorDuringCapture(false));
    if(GEngine && GEngine->GameViewport) GEngine->GameViewport->SetMouseCaptureMode(EMouseCaptureMode::NoCapture);
}
void AMuseumController::PreviousPhoto()
{
    if(bGallery && Albums.IsValidIndex(AlbumIndex))
        OpenAlbum(AlbumIndex,(PhotoIndex+Albums[AlbumIndex].Photos.Num()-1)%Albums[AlbumIndex].Photos.Num());
}
void AMuseumController::NextPhoto()
{
    if(bGallery && Albums.IsValidIndex(AlbumIndex))
        OpenAlbum(AlbumIndex,(PhotoIndex+1)%Albums[AlbumIndex].Photos.Num());
}

void AMuseumController::RebuildGallery()
{
    RemoveGalleryWidget();
    if(!GEngine || !GEngine->GameViewport) return;
    TWeakObjectPtr<AMuseumController> Weak(this);
    auto List=SNew(SScrollBox);
    auto Header=SNew(STextBlock).ColorAndOpacity(FLinearColor::White)
        .Text(FText::FromString(TEXT("COLLECTING MOMENTS")));
    auto Button=[Weak](const FString& Text, TFunction<void(AMuseumController*)> Action)
    {
        return SNew(SButton).ContentPadding(FMargin(14,9))
            .OnClicked_Lambda([Weak,Action](){ if(Weak.IsValid()) Action(Weak.Get()); return FReply::Handled(); })
            [ SNew(STextBlock).Text(FText::FromString(Text)).ColorAndOpacity(FLinearColor(0.9f,0.91f,0.93f)) ];
    };
    if(AlbumIndex==INDEX_NONE)
    {
        for(int32 I=0;I<Albums.Num();++I)
            List->AddSlot().Padding(0,0,0,6)
            [ Button(FString::Printf(TEXT("%s   ·   %d 张"),*Albums[I].Title,Albums[I].Photos.Num()),
                     [I](AMuseumController* C){ C->OpenAlbum(I); }) ];
    }
    else
    {
        const auto& Album=Albums[AlbumIndex];
        Header->SetText(FText::FromString(FString::Printf(TEXT("%s   ·   %d / %d"),*Album.Title,PhotoIndex+1,Album.Photos.Num())));
        List->AddSlot().Padding(0,0,0,12)
        [ Button(TEXT("← 全部合集"),[](AMuseumController* C){
            ++C->RequestGeneration; C->AlbumIndex=INDEX_NONE;
            C->PhotoBrush->SetResourceObject(nullptr); C->CurrentPhoto=nullptr; C->RebuildGallery(); }) ];
        for(int32 P=0;P<Album.Photos.Num();++P)
        {
            FString Label=FString::Printf(TEXT("%s%d   %s"),P==PhotoIndex?TEXT("● "):TEXT(""),P+1,*Album.Photos[P].Name);
            const int32 A=AlbumIndex;
            List->AddSlot().Padding(0,0,0,3)
            [ Button(Label,[A,P](AMuseumController* C){ C->OpenAlbum(A,P); }) ];
        }
    }
    auto ImageArea=SNew(SBox).WidthOverride(1440).HeightOverride(1000)
        [ SNew(SScaleBox).Stretch(EStretch::ScaleToFit)
          [ SNew(SImage).Image(PhotoBrush.Get()) ] ];
    if(AlbumIndex==INDEX_NONE)
    {
        ImageArea->SetContent(SNew(SBox).HAlign(HAlign_Center).VAlign(VAlign_Center)
          [SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
              [SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",24))
                .Text(FText::FromString(TEXT("COLLECTING MOMENTS"))).ColorAndOpacity(FLinearColor(0.8f,0.83f,0.86f))]
            + SVerticalBox::Slot().AutoHeight().Padding(0,18).HAlign(HAlign_Center)
              [SNew(STextBlock).Text(FText::FromString(TEXT("选择左侧的合集，打开你的回忆"))).ColorAndOpacity(FLinearColor(0.55f,0.62f,0.68f))]]);
    }
    SAssignNew(GalleryWidget,SBorder).Padding(28)
        .BorderBackgroundColor(FLinearColor(0.012f,0.018f,0.024f,0.97f))
        [ SNew(SVerticalBox)
          + SVerticalBox::Slot().AutoHeight().Padding(0,0,0,16)
            [ SNew(SHorizontalBox)
              + SHorizontalBox::Slot().FillWidth(1)[Header]
              + SHorizontalBox::Slot().AutoWidth()[Button(TEXT("关闭  Esc"),[](AMuseumController* C){ C->CloseGallery(); })] ]
          + SVerticalBox::Slot().FillHeight(1)
            [ SNew(SHorizontalBox)
              + SHorizontalBox::Slot().AutoWidth().Padding(0,0,20,0)[SNew(SBox).WidthOverride(310)[List]]
              + SHorizontalBox::Slot().FillWidth(1)[ImageArea] ]
          + SVerticalBox::Slot().AutoHeight().Padding(0,14,0,0)
            [ SNew(SHorizontalBox)
              + SHorizontalBox::Slot().AutoWidth()[Button(TEXT("← 上一张"),[](AMuseumController* C){ C->PreviousPhoto(); })]
              + SHorizontalBox::Slot().AutoWidth().Padding(12,0)[Button(TEXT("下一张 →"),[](AMuseumController* C){ C->NextPhoto(); })]
              + SHorizontalBox::Slot().FillWidth(1).HAlign(HAlign_Right)
                [SNew(STextBlock).Text(FText::FromString(TEXT("本地馆藏 · 方向键切换照片"))).ColorAndOpacity(FLinearColor(0.55f,0.62f,0.68f))] ] ];
    GEngine->GameViewport->AddViewportWidgetContent(GalleryWidget.ToSharedRef(),20);
    SetInputMode(FInputModeGameAndUI().SetWidgetToFocus(GalleryWidget).SetHideCursorDuringCapture(false));
}

void AMuseumController::RequestPhoto()
{
    const int32 Generation=++RequestGeneration;
    PhotoBrush->SetResourceObject(nullptr); CurrentPhoto=nullptr;
    const FString Path=Albums[AlbumIndex].Photos[PhotoIndex].File;
    // Decode one JPEG on a worker. Full collection images never enter GPU memory
    // together and opening a photo does not block camera rendering.
    auto* Module=&FModuleManager::LoadModuleChecked<IImageWrapperModule>(TEXT("ImageWrapper"));
    TWeakObjectPtr<AMuseumController> Weak(this);
    Async(EAsyncExecution::ThreadPool,[Weak,Generation,Path,Module]()
    {
        TArray<uint8> Compressed; TArray64<uint8> Pixels;
        if(!FFileHelper::LoadFileToArray(Compressed,*Path)) return;
        auto Wrapper=Module->CreateImageWrapper(EImageFormat::JPEG);
        if(!Wrapper.IsValid() || !Wrapper->SetCompressed(Compressed.GetData(),Compressed.Num())) return;
        if(!Wrapper->GetRaw(ERGBFormat::BGRA,8,Pixels)) return;
        const int32 W=Wrapper->GetWidth(),H=Wrapper->GetHeight();
        if(W<1 || H<1 || W>8192 || H>8192 || Pixels.Num()!=int64(W)*H*4) return;
        AsyncTask(ENamedThreads::GameThread,[Weak,Generation,W,H,Pixels=MoveTemp(Pixels)]() mutable
        { if(Weak.IsValid()) Weak->ApplyPhoto(Generation,W,H,MoveTemp(Pixels)); });
    });
}
void AMuseumController::ApplyPhoto(int32 Generation,int32 Width,int32 Height,TArray64<uint8>&& Pixels)
{
    if(Generation!=RequestGeneration || !bGallery || !Albums.IsValidIndex(AlbumIndex)) return;
    UTexture2D* Texture=UTexture2D::CreateTransient(Width,Height,PF_B8G8R8A8);
    if(!Texture || !Texture->GetPlatformData()) return;
    Texture->SRGB=true;
    auto& Mip=Texture->GetPlatformData()->Mips[0];
    void* Data=Mip.BulkData.Lock(LOCK_READ_WRITE);
    FMemory::Memcpy(Data,Pixels.GetData(),Pixels.Num());
    Mip.BulkData.Unlock(); Texture->UpdateResource();
    CurrentPhoto=Texture;
    PhotoBrush->SetResourceObject(Texture);
    PhotoBrush->ImageSize=FVector2D(Width,Height);
    RebuildGallery();
}
void AMuseumController::FastStart(){ bFast=true; if(auto* C=Cast<AMuseumCharacter>(GetPawn())) C->GetCharacterMovement()->MaxWalkSpeed=520; }
void AMuseumController::FastEnd(){ bFast=false; if(auto* C=Cast<AMuseumCharacter>(GetPawn())) C->GetCharacterMovement()->MaxWalkSpeed=260; }
void AMuseumController::TeleportToTag(FName Tag)
{
    CloseGallery();
    for(TActorIterator<AActor> It(GetWorld());It;++It)
        if(It->ActorHasTag(Tag) && GetPawn())
        {
            if(auto* MuseumPawn=Cast<AMuseumCharacter>(GetPawn())) MuseumPawn->GetCharacterMovement()->StopMovementImmediately();
            GetPawn()->TeleportTo(It->GetActorLocation(),It->GetActorRotation());
            SetControlRotation(It->GetActorRotation()); return;
        }
}
void AMuseumController::GoEntry(){ TeleportToTag(TEXT("MuseumEntry")); }
void AMuseumController::GoGarden(){ TeleportToTag(TEXT("MuseumGarden")); }
void AMuseumController::ToggleQuality()
{
    bHighQuality=!bHighQuality;
    ConsoleCommand(bHighQuality?TEXT("r.ScreenPercentage 83.333"):TEXT("r.ScreenPercentage 66.667"),false);
    ConsoleCommand(bHighQuality?TEXT("sg.GlobalIlluminationQuality 3"):TEXT("sg.GlobalIlluminationQuality 2"),false);
    ConsoleCommand(bHighQuality?TEXT("sg.ReflectionQuality 3"):TEXT("sg.ReflectionQuality 2"),false);
    if(GEngine) GEngine->AddOnScreenDebugMessage(-1,3,FColor::White,bHighQuality?TEXT("画质优先"):TEXT("流畅优先"));
}
void AMuseumController::ToggleStats(){ ConsoleCommand(TEXT("stat fps"),false); }
void AMuseumController::EndPlay(const EEndPlayReason::Type Reason)
{
    ++RequestGeneration; RemoveGalleryWidget();
    if(HintWidget.IsValid() && GEngine && GEngine->GameViewport)
        GEngine->GameViewport->RemoveViewportWidgetContent(HintWidget.ToSharedRef());
    HintWidget.Reset();
    if(InputSurface.IsValid() && GEngine && GEngine->GameViewport) GEngine->GameViewport->RemoveViewportWidgetContent(InputSurface.ToSharedRef());
    InputSurface.Reset();
    Super::EndPlay(Reason);
}

void AMuseumController::RunMuseumQA(float DeltaTime)
{
    if(!GetPawn()) return;
    if(!bQAInitialised){ QARotation=GetControlRotation(); bQAInitialised=true; }
    QATime+=DeltaTime;
    if(QATime>=4 && QATime<24)
    {
        FRotator Rotation=QARotation;
        Rotation.Yaw+=FMath::Sin((QATime-4)*0.7f)*50;
        Rotation.Pitch=FMath::Sin(QATime*0.4f)*5;
        SetControlRotation(Rotation);
        if(QATime<10) Forward(0.35f);
        else if(QATime<14) Right(0.35f);
        else if(QATime<19) Forward(-0.25f);
        if(QATime>6) QAMovingFrameTimes.Add(DeltaTime*1000);
    }
    auto Shot=[this](const TCHAR* Name)
    {
        FVector CameraLocation; FRotator CameraRotation;
        GetPlayerViewPoint(CameraLocation,CameraRotation);
        FHitResult Ground;
        GetWorld()->LineTraceSingleByChannel(Ground,GetPawn()->GetActorLocation(),GetPawn()->GetActorLocation()-FVector(0,0,10000),ECC_Visibility,FCollisionQueryParams(TEXT("QAGround"),true,GetPawn()));
        int32 Actors=0,Exhibits=0;
        for(TActorIterator<AActor> It(GetWorld());It;++It){ ++Actors; if(It->ActorHasTag(TEXT("MuseumExhibit"))) ++Exhibits; }
        UE_LOG(LogMomentMuseum,Display,TEXT("QA %s pawn=%s camera=%s actors=%d exhibits=%d ground=%s hit=%s"),Name,*GetPawn()->GetActorLocation().ToString(),*CameraLocation.ToString(),Actors,Exhibits,*GetNameSafe(Ground.GetActor()),*Ground.Location.ToString());
        FScreenshotRequest::RequestScreenshot(FPaths::Combine(QADirectory,Name),true,false);
    };
    if(QAStep==0 && QATime>=4){ Shot(TEXT("RTX_Stationary.png")); ConsoleCommand(TEXT("csvprofile start"),false); ++QAStep; }
    if(QAStep==1 && QATime>=9){ Shot(TEXT("RTX_Moving_A.png")); ++QAStep; }
    if(QAStep==2 && QATime>=18){ Shot(TEXT("RTX_Moving_B.png")); ++QAStep; }
    if(QAStep==3 && QATime>=24){ ConsoleCommand(TEXT("csvprofile stop"),false); GoGarden(); ++QAStep; }
    if(QAStep==4 && QATime>=29){ Shot(TEXT("Winter_Garden.png")); ++QAStep; }
    if(QAStep==5 && QATime>=30){ GoEntry(); ++QAStep; }
    if(QAStep==6 && QATime>=32)
    {
        FVector CameraLocation; FRotator CameraRotation;
        GetPlayerViewPoint(CameraLocation,CameraRotation);
        FCollisionQueryParams Params(TEXT("MuseumQAPick"),true,GetPawn());
        for(TActorIterator<AActor> It(GetWorld());It;++It)
        {
            if(!It->ActorHasTag(TEXT("MuseumExhibit"))) continue;
            FVector Center,Extent; It->GetActorBounds(false,Center,Extent);
            FHitResult Hit;
            if(GetWorld()->LineTraceSingleByChannel(Hit,CameraLocation,Center,ECC_Visibility,Params)
                && Hit.GetActor()==*It)
            { bQARayPick=OpenExhibit(*It); if(bQARayPick) break; }
        }
        ++QAStep;
    }
    if(QAStep==7 && QATime>=35){ Shot(TEXT("Collection.png")); ++QAStep; }
    if(QAStep==8 && QATime>=38)
    {
        QAMovingFrameTimes.Sort();
        float Sum=0; for(float T:QAMovingFrameTimes) Sum+=T;
        auto Report=MakeShared<FJsonObject>();
        Report->SetStringField(TEXT("engine"),FEngineVersion::Current().ToString());
        if(GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport)
        {
            FIntPoint Size=GEngine->GameViewport->Viewport->GetSizeXY();
            Report->SetNumberField(TEXT("output_width"),Size.X);
            Report->SetNumberField(TEXT("output_height"),Size.Y);
        }
        Report->SetStringField(TEXT("preset"),bHighQuality?TEXT("Quality"):TEXT("Balanced"));
        Report->SetNumberField(TEXT("moving_frames"),QAMovingFrameTimes.Num());
        if(QAMovingFrameTimes.Num()>0)
        {
            Report->SetNumberField(TEXT("moving_mean_ms"),Sum/QAMovingFrameTimes.Num());
            Report->SetNumberField(TEXT("moving_mean_fps"),QAMovingFrameTimes.Num()*1000.f/Sum);
            Report->SetNumberField(TEXT("moving_p99_ms"),QAMovingFrameTimes[FMath::Clamp(int32(QAMovingFrameTimes.Num()*0.99f),0,QAMovingFrameTimes.Num()-1)]);
        }
        Report->SetNumberField(TEXT("albums"),Albums.Num());
        int32 Count=0; for(const auto& A:Albums) Count+=A.Photos.Num();
        Report->SetNumberField(TEXT("photos"),Count);
        Report->SetBoolField(TEXT("ray_pick_opened_collection"),bQARayPick);
        Report->SetBoolField(TEXT("full_photo_decoded"),CurrentPhoto!=nullptr);
        Report->SetBoolField(TEXT("ray_tracing_supported"),GRHISupportsRayTracing);
        for(const TCHAR* Name:{TEXT("r.RayTracing"),TEXT("r.Lumen.HardwareRayTracing"),TEXT("r.ScreenPercentage"),TEXT("r.PathTracing")})
            if(auto* Variable=IConsoleManager::Get().FindConsoleVariable(Name)) Report->SetNumberField(Name,Variable->GetFloat());
        FString Json; FJsonSerializer::Serialize(Report,TJsonWriterFactory<>::Create(&Json));
        FFileHelper::SaveStringToFile(Json,*FPaths::Combine(QADirectory,TEXT("RuntimeQA.json")));
        bMuseumQA=false;
        ConsoleCommand(TEXT("quit"),false);
    }
}
