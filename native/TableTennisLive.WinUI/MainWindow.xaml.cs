using Microsoft.UI.Xaml;
using Microsoft.UI.Windowing;
using System.Text.Json;

// To learn more about WinUI, the WinUI project structure,
// and more about our project templates, see: http://aka.ms/winui-project-info.

namespace TableTennisLive_WinUI;

/// <summary>
/// The application window. This hosts a Frame that displays pages. Add your
/// UI and logic to MainPage.xaml / MainPage.xaml.cs instead of here so you
/// can use Page features such as navigation events and the Loaded lifecycle.
/// </summary>
public sealed partial class MainWindow : Window
{
    private readonly string _windowStatePath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "TableTennisLive", "window.json");
    private int _normalWidth = 1280;
    private int _normalHeight = 820;

    public MainWindow()
    {
        InitializeComponent();

        ExtendsContentIntoTitleBar = true;
        SetTitleBar(AppTitleBar);

        AppWindow.SetIcon("Assets/AppIcon.ico");

        RestoreWindow();
        AppWindow.Changed += (_, args) =>
        {
            if (args.DidSizeChange && AppWindow.Presenter is OverlappedPresenter
                { State: OverlappedPresenterState.Restored })
            {
                _normalWidth = AppWindow.Size.Width;
                _normalHeight = AppWindow.Size.Height;
            }
        };
        Closed += (_, _) => SaveWindow();

        // Navigate the root frame to the main page on startup.
        RootFrame.Navigate(typeof(MainShellPage));
    }

    private void RestoreWindow()
    {
        try
        {
            if (!File.Exists(_windowStatePath)) return;
            var state = JsonSerializer.Deserialize<WindowState>(File.ReadAllText(_windowStatePath));
            if (state is null) return;
            _normalWidth = Math.Clamp(state.Width, 900, 3000);
            _normalHeight = Math.Clamp(state.Height, 650, 2000);
            AppWindow.Resize(new Windows.Graphics.SizeInt32(_normalWidth, _normalHeight));
            if (state.Maximized && AppWindow.Presenter is OverlappedPresenter presenter)
                presenter.Maximize();
        }
        catch { /* Invalid or unavailable saved geometry must not prevent launch. */ }
    }

    private void SaveWindow()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_windowStatePath)!);
            var maximized = AppWindow.Presenter is OverlappedPresenter
                { State: OverlappedPresenterState.Maximized };
            File.WriteAllText(_windowStatePath,
                JsonSerializer.Serialize(new WindowState(_normalWidth, _normalHeight, maximized)));
        }
        catch { /* Window shutdown is more important than geometry persistence. */ }
    }

    private sealed record WindowState(int Width, int Height, bool Maximized);
}
