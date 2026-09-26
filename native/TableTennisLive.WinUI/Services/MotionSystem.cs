using System.Numerics;
using Microsoft.UI.Composition;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Hosting;

namespace TableTennisLive_WinUI.Services;

/// <summary>GPU-composited motion only; data is committed before animations start.</summary>
public static class MotionSystem
{
    public static void Hover(UIElement element, bool entered)
    {
        // Offset is owned by XAML layout (including Canvas.Left/Top). Translation is post-layout.
        ElementCompositionPreview.SetIsTranslationEnabled(element, true);
        var visual = ElementCompositionPreview.GetElementVisual(element);
        visual.Properties.InsertVector3("Translation", Vector3.Zero);
        var compositor = visual.Compositor;
        var scale = compositor.CreateVector3KeyFrameAnimation();
        scale.InsertKeyFrame(1f, entered ? new Vector3(1.01f, 1.01f, 1f) : Vector3.One);
        scale.Duration = TimeSpan.FromMilliseconds(entered ? 180 : 220);
        visual.CenterPoint = new Vector3((float)((FrameworkElement)element).ActualSize.X / 2f,
            (float)((FrameworkElement)element).ActualSize.Y / 2f, 0f);
        visual.StartAnimation("Scale", scale);
        var lift = compositor.CreateVector3KeyFrameAnimation();
        lift.InsertKeyFrame(1f, entered ? new Vector3(0f, -2f, 0f) : Vector3.Zero);
        lift.Duration = scale.Duration;
        visual.StartAnimation("Translation", lift);
    }

    public static void Enter(UIElement element)
    {
        ElementCompositionPreview.SetIsTranslationEnabled(element, true);
        var visual = ElementCompositionPreview.GetElementVisual(element);
        visual.Properties.InsertVector3("Translation", Vector3.Zero);
        var fade = visual.Compositor.CreateScalarKeyFrameAnimation();
        fade.InsertKeyFrame(0f, 0.82f);
        fade.InsertKeyFrame(1f, 1f);
        fade.Duration = TimeSpan.FromMilliseconds(280);
        visual.StartAnimation("Opacity", fade);
        var shift = visual.Compositor.CreateVector3KeyFrameAnimation();
        shift.InsertKeyFrame(0f, new Vector3(0f, 8f, 0f));
        shift.InsertKeyFrame(1f, Vector3.Zero);
        shift.Duration = fade.Duration;
        visual.StartAnimation("Translation", shift);
    }

    public static void ScorePulse(UIElement element)
    {
        var visual = ElementCompositionPreview.GetElementVisual(element);
        var scale = visual.Compositor.CreateVector3KeyFrameAnimation();
        scale.InsertKeyFrame(0f, Vector3.One);
        scale.InsertKeyFrame(0.42f, new Vector3(1.025f, 1.025f, 1f));
        scale.InsertKeyFrame(1f, Vector3.One);
        scale.Duration = TimeSpan.FromMilliseconds(300);
        visual.CenterPoint = new Vector3((float)((FrameworkElement)element).ActualSize.X / 2f,
            (float)((FrameworkElement)element).ActualSize.Y / 2f, 0f);
        visual.StartAnimation("Scale", scale);
    }

    public static void ScoreChange(Microsoft.UI.Xaml.Controls.TextBlock previous,
        Microsoft.UI.Xaml.Controls.TextBlock current, string oldValue, string newValue)
    {
        if (oldValue == newValue) return;
        ElementCompositionPreview.SetIsTranslationEnabled(previous, true);
        ElementCompositionPreview.SetIsTranslationEnabled(current, true);
        previous.Text = oldValue;
        var oldVisual = ElementCompositionPreview.GetElementVisual(previous);
        var newVisual = ElementCompositionPreview.GetElementVisual(current);
        oldVisual.Properties.InsertVector3("Translation", Vector3.Zero);
        newVisual.Properties.InsertVector3("Translation", Vector3.Zero);
        oldVisual.StopAnimation("Translation");
        oldVisual.StopAnimation("Opacity");
        newVisual.StopAnimation("Translation");
        newVisual.StopAnimation("Opacity");
        // The bound score is already current; this only decorates the new state.
        var compositor = newVisual.Compositor;
        var slideOld = compositor.CreateVector3KeyFrameAnimation();
        slideOld.InsertKeyFrame(0f, Vector3.Zero);
        slideOld.InsertKeyFrame(1f, new Vector3(0f, -16f, 0f));
        slideOld.Duration = TimeSpan.FromMilliseconds(220);
        var fadeOld = compositor.CreateScalarKeyFrameAnimation();
        fadeOld.InsertKeyFrame(0f, 0.65f);
        fadeOld.InsertKeyFrame(1f, 0f);
        fadeOld.Duration = slideOld.Duration;
        oldVisual.StartAnimation("Translation", slideOld);
        oldVisual.StartAnimation("Opacity", fadeOld);
        var slideNew = compositor.CreateVector3KeyFrameAnimation();
        slideNew.InsertKeyFrame(0f, new Vector3(0f, 14f, 0f));
        slideNew.InsertKeyFrame(1f, Vector3.Zero);
        slideNew.Duration = TimeSpan.FromMilliseconds(250);
        var fadeNew = compositor.CreateScalarKeyFrameAnimation();
        fadeNew.InsertKeyFrame(0f, 0.72f);
        fadeNew.InsertKeyFrame(1f, 1f);
        fadeNew.Duration = slideNew.Duration;
        newVisual.StartAnimation("Translation", slideNew);
        newVisual.StartAnimation("Opacity", fadeNew);
        ScorePulse(current);
    }
}
