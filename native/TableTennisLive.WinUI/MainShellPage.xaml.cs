using System.ComponentModel;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media.Imaging;
using Microsoft.UI.Xaml.Media.Animation;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Shapes;
using Microsoft.Windows.Storage.Pickers;
using Microsoft.Windows.AppNotifications;
using Microsoft.Windows.AppNotifications.Builder;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Services;
using TableTennisLive_WinUI.Services;
using TableTennisLive_WinUI.ViewModels;

namespace TableTennisLive_WinUI;

public sealed partial class MainShellPage : Page
{
    public MainViewModel ViewModel { get; }
    private CancellationTokenSource? _detailCancellation;
    private CancellationTokenSource? _drawCancellation;
    private bool _wttDrawMode;
    private bool _asianDrawMode;
    private string _returnSection = "home";
    private bool _initialized;
    private MatchItemViewModel? _observedDetail;
    private string _lastDetailScore = "";
    private MiniScoreWindow? _miniWindow;
    private bool _drawPointerDown;
    private bool _drawDragging;
    private bool _suppressDrawTap;
    private Windows.Foundation.Point _drawPointerStart;
    private double _drawStartHorizontal;
    private double _drawStartVertical;
    private readonly List<(TrendPoint Point, double X, double Y)> _renderedTrend = [];
    private Line? _trendGuide;

    public MainShellPage()
    {
        InitializeComponent();
        DrawScroller.AddHandler(UIElement.PointerPressedEvent,
            new PointerEventHandler(DrawPointerPressed), true);
        DrawScroller.AddHandler(UIElement.PointerMovedEvent,
            new PointerEventHandler(DrawPointerMoved), true);
        DrawScroller.AddHandler(UIElement.PointerReleasedEvent,
            new PointerEventHandler(DrawPointerReleased), true);
        DrawScroller.AddHandler(UIElement.PointerCanceledEvent,
            new PointerEventHandler(DrawPointerReleased), true);
        ViewModel = new MainViewModel(DispatcherQueue);
        DataContext = ViewModel;
        ViewModel.PropertyChanged += ViewModel_PropertyChanged;
        ViewModel.TrendChanged += RenderTrend;
        ViewModel.AlertRaised += ShowAlert;
        ViewModel.Matches.CollectionChanged += (_, _) => UpdateEmptyState();
        Navigation.SelectedItem = Navigation.MenuItems[0];
        DrawProjectSelect.ItemsSource = new[] { "男单", "女单", "男双", "女双", "混双" };
        RequestedTheme = ElementTheme.Light;
        StartAlertSwitch.IsOn = ViewModel.AlertEnabled("start");
        ScoreAlertSwitch.IsOn = ViewModel.AlertEnabled("score");
        FinalAlertSwitch.IsOn = ViewModel.AlertEnabled("final");
        var notificationReady = ((App)Application.Current).NotificationsReady;
        StartAlertSwitch.IsEnabled = ScoreAlertSwitch.IsEnabled =
            FinalAlertSwitch.IsEnabled = notificationReady;
        _initialized = true;
        UpdateEmptyState();
        Unloaded += async (_, _) =>
        {
            _detailCancellation?.Cancel();
            _drawCancellation?.Cancel();
            if (_observedDetail is not null)
                _observedDetail.PropertyChanged -= DetailItem_PropertyChanged;
            ViewModel.TrendChanged -= RenderTrend;
            ViewModel.AlertRaised -= ShowAlert;
            await ViewModel.DisposeAsync();
        };
    }

    private void ViewModel_PropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(MainViewModel.IsDetail))
        {
            MatchList.Visibility = ViewModel.IsDetail ? Visibility.Collapsed : Visibility.Visible;
            DetailView.Visibility = ViewModel.IsDetail ? Visibility.Visible : Visibility.Collapsed;
            RankingsView.Visibility = Visibility.Collapsed;
            if (ViewModel.IsDetail)
            {
                DrawsView.Visibility = Visibility.Collapsed;
                DetailView.ChangeView(0, 0, null);
            }
            else MotionSystem.Enter(MatchList);
            UpdateEmptyState();
        }
    }

    private void Navigation_SelectionChanged(NavigationView sender,
        NavigationViewSelectionChangedEventArgs args)
    {
        if (!_initialized && ViewModel is null) return;
        if (args.IsSettingsSelected)
        {
            MatchList.Visibility = Visibility.Collapsed;
            DetailView.Visibility = Visibility.Collapsed;
            RankingsView.Visibility = Visibility.Collapsed;
            DrawsView.Visibility = Visibility.Collapsed;
            MajorTabs.Visibility = Visibility.Collapsed;
            WttTabs.Visibility = Visibility.Collapsed;
            AsianTabs.Visibility = Visibility.Collapsed;
            SettingsView.Visibility = Visibility.Visible;
            UpdateEmptyState();
            return;
        }
        SettingsView.Visibility = Visibility.Collapsed;
        if (args.SelectedItem is NavigationViewItem item && item.Tag is string section)
        {
            _drawCancellation?.Cancel();
            _wttDrawMode = false;
            _asianDrawMode = false;
            ViewModel.SelectSection(section);
            MajorTabs.Visibility = section == "majors" ? Visibility.Visible : Visibility.Collapsed;
            WttTabs.Visibility = section == "wtt" ? Visibility.Visible : Visibility.Collapsed;
            AsianTabs.Visibility = section == "majors" && ViewModel.MajorCategory == "亚运会"
                ? Visibility.Visible : Visibility.Collapsed;
            DrawsView.Visibility = Visibility.Collapsed;
            MatchList.Visibility = section == "rankings" ? Visibility.Collapsed : Visibility.Visible;
            DetailView.Visibility = Visibility.Collapsed;
            RankingsView.Visibility = section == "rankings" ? Visibility.Visible : Visibility.Collapsed;
            MotionSystem.Enter(section == "rankings" ? RankingsView : MatchList);
            UpdateEmptyState();
        }
    }

    private void SearchBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (ViewModel is null) return;
        ViewModel.Search(SearchBox.Text);
        SettingsView.Visibility = Visibility.Collapsed;
        DetailView.Visibility = Visibility.Collapsed;
        RankingsView.Visibility = Visibility.Collapsed;
        DrawsView.Visibility = Visibility.Collapsed;
        MajorTabs.Visibility = Visibility.Collapsed;
        WttTabs.Visibility = Visibility.Collapsed;
        AsianTabs.Visibility = Visibility.Collapsed;
        MatchList.Visibility = Visibility.Visible;
        UpdateEmptyState();
    }

    private void UpdateEmptyState()
    {
        if (ViewModel is null || EmptyView is null || MatchList is null) return;
        EmptyView.Visibility = MatchList.Visibility == Visibility.Visible &&
            ViewModel.Matches.Count == 0 && !ViewModel.IsDetail
            ? Visibility.Visible : Visibility.Collapsed;
        EmptyMessage.Text = ViewModel.SectionTitle switch
        {
            "WTT" => "当前没有进行中或近期开赛的主要 WTT 比赛。可切换至签表，或稍后刷新。",
            "中国乒超" => "暂未接入可靠的公开实时比分来源，不会把旧比赛标为 LIVE。",
            "我的关注" => "还没有关注的比赛。点击比赛卡片上的星标即可收藏。",
            "实时比分" => "当前没有官网标记为 LIVE 的比赛。",
            "今日赛程" => "今天暂无可显示的赛程。",
            _ => "当前筛选下没有比赛。请切换赛事或稍后刷新。"
        };
    }

    private async void WttMode_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: string mode }) return;
        ExitDetailForSection("wtt");
        _wttDrawMode = mode == "draws";
        _asianDrawMode = false;
        MatchList.Visibility = _wttDrawMode ? Visibility.Collapsed : Visibility.Visible;
        DrawsView.Visibility = _wttDrawMode ? Visibility.Visible : Visibility.Collapsed;
        UpdateEmptyState();
        if (!_wttDrawMode) { _drawCancellation?.Cancel(); return; }
        DrawEventSelect.Visibility = Visibility.Visible;
        DrawProjectSelect.ItemsSource = new[] { "男单", "女单", "男双", "女双", "混双" };
        Grid.SetColumn(DrawProjectSelect, 1);
        Grid.SetColumnSpan(DrawProjectSelect, 1);
        if (DrawProjectSelect.SelectedIndex < 0) DrawProjectSelect.SelectedIndex = 0;
        if (ViewModel.WttEvents.Count == 0)
        {
            _drawCancellation?.Cancel();
            _drawCancellation = new CancellationTokenSource();
            await ViewModel.LoadWttEventsAsync(_drawCancellation.Token);
            if (_wttDrawMode && ViewModel.WttEvents.Count > 0 && DrawEventSelect.SelectedIndex < 0)
                DrawEventSelect.SelectedIndex = 0;
        }
        MotionSystem.Enter(DrawsView);
    }

    private async void DrawSelection_Changed(object sender, SelectionChangedEventArgs e)
    {
        if ((!_wttDrawMode && !_asianDrawMode) ||
            DrawProjectSelect.SelectedItem is not string project) return;
        if (_wttDrawMode && DrawEventSelect.SelectedItem is not DrawEvent) return;
        _drawCancellation?.Cancel();
        var request = new CancellationTokenSource();
        _drawCancellation = request;
        if (_wttDrawMode)
            await ViewModel.LoadWttDrawAsync(((DrawEvent)DrawEventSelect.SelectedItem).Id,
                project, request.Token);
        else await ViewModel.LoadAsianDrawAsync(project, request.Token);
        if (!request.IsCancellationRequested && ViewModel.WttStages.Count > 0)
            DrawStageSelect.SelectedIndex = 0;
    }

    private void DrawStage_Changed(object sender, SelectionChangedEventArgs e)
    {
        ViewModel.SelectDrawStage(DrawStageSelect.SelectedItem as DrawStage);
        RenderBracket();
        DrawScroller.ChangeView(0, 0, null);
    }

    private void RenderBracket()
    {
        if (DrawCanvas is null) return;
        var rounds = ViewModel.DrawRounds.ToArray();
        var geometry = BracketLayout.Build(rounds);
        var edgeBrush = new SolidColorBrush(
            Windows.UI.Color.FromArgb(255, 204, 213, 225));
        DrawCanvas.Children.Clear();
        DrawCanvas.Width = geometry.Width;
        DrawCanvas.Height = geometry.Height;
        for (var index = 0; index < rounds.Length; index++)
        {
            var title = new TextBlock
            {
                Text = rounds[index].Title,
                FontSize = 16,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold
            };
            Canvas.SetLeft(title, 20 + index * (BracketLayout.CardWidth + BracketLayout.ColumnGap));
            Canvas.SetTop(title, 14);
            DrawCanvas.Children.Add(title);
        }
        foreach (var edge in geometry.Edges)
        {
            var centerY = edge.From.Y + BracketLayout.CardHeight / 2;
            var targetY = edge.To.Y + BracketLayout.CardHeight / 2;
            var startX = edge.From.X + BracketLayout.CardWidth;
            var endX = edge.To.X;
            var middle = (startX + endX) / 2;
            var path = new Microsoft.UI.Xaml.Shapes.Path
            {
                Stroke = edgeBrush,
                StrokeThickness = 1.6,
                Data = new PathGeometry
                {
                    Figures =
                    {
                        new PathFigure
                        {
                            StartPoint = new Windows.Foundation.Point(startX, centerY),
                            Segments =
                            {
                                new BezierSegment
                                {
                                    Point1 = new Windows.Foundation.Point(middle, centerY),
                                    Point2 = new Windows.Foundation.Point(middle, targetY),
                                    Point3 = new Windows.Foundation.Point(endX, targetY)
                                }
                            }
                        }
                    }
                }
            };
            DrawCanvas.Children.Add(path);
        }
        foreach (var node in geometry.Nodes)
        {
            var card = CreateBracketCard(node.Match, false);
            Canvas.SetLeft(card, node.X);
            Canvas.SetTop(card, node.Y);
            DrawCanvas.Children.Add(card);
        }
    }

    private Border CreateBracketCard(DrawMatch match, bool dark)
    {
        var border = new Border
        {
            Width = BracketLayout.CardWidth,
            Height = BracketLayout.CardHeight,
            CornerRadius = new CornerRadius(13),
            Padding = new Thickness(13, 10, 13, 8),
            BorderThickness = new Thickness(1.4),
            BorderBrush = new SolidColorBrush(dark
                ? Windows.UI.Color.FromArgb(255, 76, 86, 103)
                : Windows.UI.Color.FromArgb(255, 207, 217, 230)),
            Background = new SolidColorBrush(dark
                ? Windows.UI.Color.FromArgb(255, 42, 47, 57)
                : Windows.UI.Color.FromArgb(255, 255, 255, 255)),
            Tag = match
        };
        var body = new StackPanel { Spacing = 7 };
        foreach (var player in new[] { match.Left, match.Right })
        {
            var row = new Grid { ColumnSpacing = 8, Height = 26 };
            row.ColumnDefinitions.Add(new ColumnDefinition
                { Width = new GridLength(1, GridUnitType.Star) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(30) });
            var playerLine = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                Spacing = 6,
                VerticalAlignment = VerticalAlignment.Center
            };
            var flagUri = CountryFlags.AssetUri(player.CountryCode.ToUpperInvariant());
            if (flagUri.Length > 0)
            {
                var flagHost = new Grid { Width = 23, Height = 16 };
                var fallback = new TextBlock
                {
                    Text = player.CountryCode,
                    FontSize = 10,
                    VerticalAlignment = VerticalAlignment.Center
                };
                flagHost.Children.Add(fallback);
                var flag = new Image
                {
                    Source = new BitmapImage(new Uri(flagUri)),
                    Width = 23,
                    Height = 16,
                    Stretch = Stretch.UniformToFill
                };
                flag.ImageOpened += (_, _) => fallback.Visibility = Visibility.Collapsed;
                flag.ImageFailed += (_, _) => flag.Visibility = Visibility.Collapsed;
                flagHost.Children.Add(flag);
                playerLine.Children.Add(flagHost);
            }
            var name = new TextBlock
            {
                Text = player.Name,
                TextTrimming = TextTrimming.CharacterEllipsis,
                MaxWidth = flagUri.Length > 0 ? 210 : 240,
                VerticalAlignment = VerticalAlignment.Center,
                FontWeight = player.Winner ? Microsoft.UI.Text.FontWeights.Bold :
                    Microsoft.UI.Text.FontWeights.Normal
            };
            if (player.Winner)
                name.Foreground = new SolidColorBrush(Windows.UI.Color.FromArgb(255, 37, 99, 235));
            playerLine.Children.Add(name);
            row.Children.Add(playerLine);
            var score = new TextBlock
            {
                Text = player.Score,
                TextAlignment = TextAlignment.Right,
                VerticalAlignment = VerticalAlignment.Center,
                FontWeight = player.Winner ? Microsoft.UI.Text.FontWeights.Bold :
                    Microsoft.UI.Text.FontWeights.Normal
            };
            Grid.SetColumn(score, 1);
            row.Children.Add(score);
            body.Children.Add(row);
        }
        body.Children.Add(new Border
        {
            Height = 1,
            Background = new SolidColorBrush(dark
                ? Windows.UI.Color.FromArgb(255, 72, 80, 93)
                : Windows.UI.Color.FromArgb(255, 226, 232, 240))
        });
        var caption = match.Bye ? "轮空晋级" : match.Left.Winner || match.Right.Winner
            ? "已结束 · 点击查看逐局比分" : $"{match.Date}  {match.Time}".Trim();
        if (caption.Length == 0) caption = "等待官方安排";
        body.Children.Add(new TextBlock
        {
            Text = caption,
            FontSize = 11,
            Opacity = 0.66,
            TextTrimming = TextTrimming.CharacterEllipsis
        });
        border.Child = body;
        border.Tapped += DrawMatch_Tapped;
        border.PointerEntered += (_, _) =>
        {
            border.BorderBrush = new SolidColorBrush(Windows.UI.Color.FromArgb(255, 37, 99, 235));
            MotionSystem.Hover(border, true);
        };
        border.PointerExited += (_, _) =>
        {
            border.BorderBrush = new SolidColorBrush(dark
                ? Windows.UI.Color.FromArgb(255, 76, 86, 103)
                : Windows.UI.Color.FromArgb(255, 207, 217, 230));
            MotionSystem.Hover(border, false);
        };
        return border;
    }

    private void DrawZoomIn_Click(object sender, RoutedEventArgs e) =>
        DrawScroller.ChangeView(null, null, Math.Min(2.5f, DrawScroller.ZoomFactor * 1.2f));

    private void DrawZoomOut_Click(object sender, RoutedEventArgs e) =>
        DrawScroller.ChangeView(null, null, Math.Max(0.35f, DrawScroller.ZoomFactor / 1.2f));

    private void DrawFit_Click(object sender, RoutedEventArgs e)
    {
        if (DrawCanvas.Width <= 0 || DrawScroller.ActualWidth <= 0) return;
        var fit = Math.Clamp((DrawScroller.ActualWidth - 24) / DrawCanvas.Width, 0.35, 2.5);
        DrawScroller.ChangeView(0, 0, (float)fit);
    }

    private void DrawScroller_ViewChanged(object sender, ScrollViewerViewChangedEventArgs e) =>
        DrawZoomLabel.Text = $"{DrawScroller.ZoomFactor:P0}";

    private void DrawPointerPressed(object sender, PointerRoutedEventArgs e)
    {
        var point = e.GetCurrentPoint(DrawScroller);
        if (!point.Properties.IsLeftButtonPressed && !point.Properties.IsMiddleButtonPressed)
            return;
        _suppressDrawTap = false;
        _drawPointerDown = true;
        _drawDragging = false;
        _drawPointerStart = point.Position;
        _drawStartHorizontal = DrawScroller.HorizontalOffset;
        _drawStartVertical = DrawScroller.VerticalOffset;
    }

    private void DrawPointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (!_drawPointerDown) return;
        var point = e.GetCurrentPoint(DrawScroller);
        if (!point.Properties.IsLeftButtonPressed && !point.Properties.IsMiddleButtonPressed)
        {
            DrawPointerReleased(sender, e);
            return;
        }
        var dx = point.Position.X - _drawPointerStart.X;
        var dy = point.Position.Y - _drawPointerStart.Y;
        if (!_drawDragging && dx * dx + dy * dy < 36) return;
        if (!_drawDragging)
        {
            _drawDragging = true;
            _suppressDrawTap = true;
            DrawScroller.CapturePointer(e.Pointer);
        }
        DrawScroller.ChangeView(_drawStartHorizontal - dx, _drawStartVertical - dy,
            null, true);
    }

    private void DrawPointerReleased(object sender, PointerRoutedEventArgs e)
    {
        _drawPointerDown = false;
        _drawDragging = false;
        DrawScroller.ReleasePointerCapture(e.Pointer);
    }

    private async void DrawMatch_Tapped(object sender, TappedRoutedEventArgs e)
    {
        if (_suppressDrawTap) { e.Handled = true; return; }
        if (sender is not Border { Tag: DrawMatch match }) return;
        var panel = new StackPanel { Spacing = 14, MinWidth = 440 };
        panel.Children.Add(new TextBlock
        {
            Text = match.Date.Length > 0 ? $"{match.Date}  {match.Time}" : "签表比赛",
            Opacity = 0.6
        });
        var players = new[] { match.Left, match.Right };
        DrawPlayer? selectedPlayer = null;
        var dialog = new ContentDialog
        {
            XamlRoot = XamlRoot,
            Title = "签表比赛详情",
            Content = panel,
            CloseButtonText = "关闭"
        };
        foreach (var player in players)
        {
            var row = new Grid { ColumnSpacing = 12 };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            var playerLabel = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 9 };
            var flagUri = CountryFlags.AssetUri(player.CountryCode);
            if (flagUri.Length > 0)
                playerLabel.Children.Add(new Image
                {
                    Source = new BitmapImage(new Uri(flagUri)), Width = 24, Height = 16,
                    Stretch = Stretch.UniformToFill
                });
            playerLabel.Children.Add(new TextBlock
            {
                Text = CountryFlags.WithoutCode(player.Name),
                VerticalAlignment = VerticalAlignment.Center
            });
            var button = new Button
            {
                Content = playerLabel,
                HorizontalAlignment = HorizontalAlignment.Left,
                Background = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Transparent),
                BorderThickness = new Thickness(0),
                Padding = new Thickness(0)
            };
            button.Click += (_, _) => { selectedPlayer = player; dialog.Hide(); };
            row.Children.Add(button);
            var score = new TextBlock
            {
                Text = player.Score,
                FontSize = 24,
                FontWeight = player.Winner ? Microsoft.UI.Text.FontWeights.Bold :
                    Microsoft.UI.Text.FontWeights.Normal
            };
            Grid.SetColumn(score, 1);
            row.Children.Add(score);
            panel.Children.Add(row);
        }
        var scorePanel = new StackPanel { Spacing = 10 };
        panel.Children.Add(scorePanel);
        RenderDrawSetScores(scorePanel, match);
        await dialog.ShowAsync();
        if (selectedPlayer is { } chosen)
            await ShowPlayerAsync(chosen.Name, chosen.Raw, chosen.CountryCode,
                chosen.PlayerId);
    }

    private void RenderDrawSetScores(StackPanel panel, DrawMatch match)
    {
        panel.Children.Clear();
        if (match.Sets.Count > 0)
        {
            panel.Children.Add(new TextBlock { Text = "逐局比分", Opacity = 0.6 });
            var strip = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
            foreach (var (set, index) in match.Sets.Select((value, position) => (value, position)))
            {
                var cell = new StackPanel { Spacing = 5, MinWidth = 58 };
                cell.Children.Add(new TextBlock
                    { Text = $"第 {index + 1} 局", FontSize = 11, Opacity = 0.6 });
                cell.Children.Add(new TextBlock
                    { Text = set.Left.ToString(), FontSize = 19, FontWeight = set.Left > set.Right
                        ? Microsoft.UI.Text.FontWeights.Bold : Microsoft.UI.Text.FontWeights.Normal });
                cell.Children.Add(new TextBlock
                    { Text = set.Right.ToString(), FontSize = 19, FontWeight = set.Right > set.Left
                        ? Microsoft.UI.Text.FontWeights.Bold : Microsoft.UI.Text.FontWeights.Normal });
                strip.Children.Add(new Border
                {
                    Child = cell, CornerRadius = new CornerRadius(9), Padding = new Thickness(9),
                    Background = new SolidColorBrush(
                        Windows.UI.Color.FromArgb(255, 238, 245, 253))
                });
            }
            panel.Children.Add(new ScrollViewer
            {
                Content = strip,
                HorizontalScrollMode = ScrollMode.Enabled,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
                VerticalScrollMode = ScrollMode.Disabled,
                VerticalScrollBarVisibility = ScrollBarVisibility.Disabled
            });
            panel.Children.Add(new TextBlock
                { Text = "上行为第一位选手，下行为第二位选手", FontSize = 12, Opacity = 0.6 });
        }
        else panel.Children.Add(new TextBlock
        {
            Text = match.Bye ? "轮空晋级" : "官网暂未发布逐局比分",
            Opacity = 0.6
        });
    }

    private void MajorCategory_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: string category }) return;
        ExitDetailForSection("majors");
        _drawCancellation?.Cancel();
        _asianDrawMode = false;
        ViewModel.SelectMajorCategory(category);
        AsianTabs.Visibility = category == "亚运会" ? Visibility.Visible : Visibility.Collapsed;
        DrawsView.Visibility = Visibility.Collapsed;
        MatchList.Visibility = Visibility.Visible;
        UpdateEmptyState();
    }

    private void AsianMode_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: string mode }) return;
        ExitDetailForSection("majors");
        _asianDrawMode = mode == "draws";
        _wttDrawMode = false;
        MatchList.Visibility = _asianDrawMode ? Visibility.Collapsed : Visibility.Visible;
        DrawsView.Visibility = _asianDrawMode ? Visibility.Visible : Visibility.Collapsed;
        UpdateEmptyState();
        if (!_asianDrawMode) { _drawCancellation?.Cancel(); return; }
        DrawEventSelect.Visibility = Visibility.Collapsed;
        Grid.SetColumn(DrawProjectSelect, 0);
        Grid.SetColumnSpan(DrawProjectSelect, 2);
        DrawProjectSelect.ItemsSource = new[] { "男单", "女单", "男双", "女双",
            "混双", "男团", "女团" };
        DrawProjectSelect.SelectedIndex = 0;
        MotionSystem.Enter(DrawsView);
    }

    private void ExitDetailForSection(string section)
    {
        if (ViewModel.IsDetail)
        {
            _detailCancellation?.Cancel();
            if (_observedDetail is not null)
                _observedDetail.PropertyChanged -= DetailItem_PropertyChanged;
            _observedDetail = null;
            ViewModel.SelectSection(section);
        }
        DetailView.Visibility = Visibility.Collapsed;
        RankingsView.Visibility = Visibility.Collapsed;
        EmptyView.Visibility = Visibility.Collapsed;
    }

    private void RankingEvent_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { Tag: string eventCode }) ViewModel.SelectRankingEvent(eventCode);
    }

    private void RankingCategory_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { Tag: string category }) ViewModel.SelectRankingCategory(category);
    }

    private void RankingContainer_ContentChanging(ListViewBase sender,
        ContainerContentChangingEventArgs args)
    {
        if (!args.InRecycleQueue && args.Item is RankingEntry row)
            _ = ViewModel.EnsureRankingPortraitAsync(row);
    }

    private void AlertOption_Toggled(object sender, RoutedEventArgs e)
    {
        if (!_initialized || sender is not ToggleSwitch { Tag: string kind } option) return;
        ViewModel.SetAlert(kind, option.IsOn);
    }

    private void ShowAlert(MatchAlert alert)
    {
        if (!((App)Application.Current).NotificationsReady) return;
        try
        {
            var notification = new AppNotificationBuilder().AddText(alert.Title)
                .AddText(alert.Message).BuildNotification();
            AppNotificationManager.Default.Show(notification);
        }
        catch { /* Windows notification settings may suppress toasts. */ }
    }

    private void PlayerA_Click(object sender, RoutedEventArgs e) => _ = ShowMatchPlayerAsync(sender, true);
    private void PlayerB_Click(object sender, RoutedEventArgs e) => _ = ShowMatchPlayerAsync(sender, false);
    private void TeamPlayerA_Click(object sender, RoutedEventArgs e) =>
        _ = ShowTeamGamePlayerAsync(sender, true);
    private void TeamPlayerB_Click(object sender, RoutedEventArgs e) =>
        _ = ShowTeamGamePlayerAsync(sender, false);

    private async Task ShowTeamGamePlayerAsync(object sender, bool first)
    {
        if (sender is not Button { Tag: TeamGameItem game }) return;
        var name = first ? game.PlayerA : game.PlayerB;
        var players = name.Split('/', StringSplitOptions.TrimEntries |
            StringSplitOptions.RemoveEmptyEntries);
        if (players.Length == 0) return;
        if (players.Length > 1)
        {
            var picker = new ComboBox { ItemsSource = players, SelectedIndex = 0, MinWidth = 280 };
            var dialog = new ContentDialog
            {
                XamlRoot = XamlRoot, Title = "选择选手", Content = picker,
                PrimaryButtonText = "查看资料", CloseButtonText = "取消"
            };
            if (await dialog.ShowAsync() != ContentDialogResult.Primary) return;
            name = players[picker.SelectedIndex];
        }
        await ShowPlayerAsync(name, name, CountryFlags.CodeFromName(name), "");
    }

    private async Task ShowMatchPlayerAsync(object sender, bool first)
    {
        if (sender is not Button { Tag: MatchItemViewModel item }) return;
        if (item.IsClubFixture) return;
        var match = item.Match;
        var display = first ? match.PlayerA : match.PlayerB;
        var raw = first ? match.PlayerARaw : match.PlayerBRaw;
        var id = first ? match.PlayerAId : match.PlayerBId;
        if (raw.Contains('/'))
        {
            var players = raw.Split('/', StringSplitOptions.TrimEntries |
                StringSplitOptions.RemoveEmptyEntries);
            var picker = new ComboBox { ItemsSource = players, SelectedIndex = 0, MinWidth = 280 };
            var choose = new ContentDialog
            {
                XamlRoot = XamlRoot, Title = "选择选手", Content = picker,
                PrimaryButtonText = "查看资料", CloseButtonText = "取消"
            };
            if (await choose.ShowAsync() != ContentDialogResult.Primary) return;
            raw = players[picker.SelectedIndex];
            display = raw;
            id = "";
        }
        var country = first ? match.PlayerACountryCode : match.PlayerBCountryCode;
        if (country.Length == 0)
        {
            var suffix = System.Text.RegularExpressions.Regex.Match(display, @"\(([A-Z]{3})\)$");
            country = suffix.Success ? suffix.Groups[1].Value : "";
        }
        await ShowPlayerAsync(display, raw, country, id);
    }

    private async void RankingPlayer_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: RankingEntry row }) return;
        if (!row.IsPair)
        {
            await ShowPlayerAsync(row.PlayerName, row.PlayerName, row.CountryCode, row.PlayerId);
            return;
        }
        var picker = new ComboBox { ItemsSource = new[] { row.PlayerName, row.PartnerName },
            SelectedIndex = 0, MinWidth = 300 };
        var dialog = new ContentDialog
        {
            XamlRoot = XamlRoot, Title = "选择选手", Content = picker,
            PrimaryButtonText = "查看资料", CloseButtonText = "取消"
        };
        if (await dialog.ShowAsync() != ContentDialogResult.Primary) return;
        if (picker.SelectedIndex == 1)
            await ShowPlayerAsync(row.PartnerName, row.PartnerName,
                row.PartnerCountryCode, row.PartnerId);
        else
            await ShowPlayerAsync(row.PlayerName, row.PlayerName, row.CountryCode, row.PlayerId);
    }

    private async Task ShowPlayerAsync(string name, string raw, string country, string id)
    {
        PlayerProfile? profile = null;
        try { profile = await ViewModel.GetPlayerProfileAsync(name, raw, country, id, CancellationToken.None); }
        catch (Exception error)
        {
            await new ContentDialog
            {
                XamlRoot = XamlRoot, Title = "选手资料暂不可用",
                Content = error.Message, CloseButtonText = "关闭"
            }.ShowAsync();
            return;
        }
        if (profile is null)
        {
            await new ContentDialog
            {
                XamlRoot = XamlRoot, Title = "无法唯一核实这位选手",
                Content = "官网未提供可确认的选手 ID；为避免打开错误的资料页，暂不显示推测资料。",
                CloseButtonText = "关闭"
            }.ShowAsync();
            return;
        }
        var panel = new StackPanel { Spacing = 12, MinWidth = 420 };
        if (profile.Portrait is not null)
            panel.Children.Add(new Image
            {
                Source = new BitmapImage(profile.Portrait), Height = 170,
                HorizontalAlignment = HorizontalAlignment.Left
            });
        panel.Children.Add(new TextBlock
        {
            Text = TableTennisLive.Core.Services.ChineseNames.Display(profile.Name),
            FontSize = 26, FontWeight = Microsoft.UI.Text.FontWeights.Bold
        });
        panel.Children.Add(new TextBlock
        {
            Text = $"{profile.CountryName}  {profile.CountryCode}  ·  世界排名 " +
                (profile.Rank is null ? "—" : $"#{profile.Rank}") +
                $"  ·  积分 {profile.Points?.ToString() ?? "—"}"
        });
        panel.Children.Add(new TextBlock
        {
            Text = $"年龄 {profile.Age?.ToString() ?? "—"}  ·  惯用手 " +
                (profile.Hand.Length > 0 ? profile.Hand : "—"),
            TextWrapping = TextWrapping.Wrap
        });
        var hasWinRate = profile.YearWins is not null && profile.YearMatches > 0;
        panel.Children.Add(new TextBlock
        {
            Text = hasWinRate
                ? $"年度胜率 {100.0 * profile.YearWins!.Value / profile.YearMatches!.Value:F1}%"
                : "年度胜率：官网暂未提供本年度胜负统计",
            FontSize = hasWinRate ? 23 : 15,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            TextWrapping = TextWrapping.Wrap
        });
        if (hasWinRate)
            panel.Children.Add(new TextBlock
            {
                Text = $"{profile.YearWins} 胜 / {profile.YearMatches} 场 · WTT 官方年度统计",
                Opacity = 0.7, TextWrapping = TextWrapping.Wrap
            });
        if (profile.Biography.Length > 0)
            panel.Children.Add(new TextBlock { Text = profile.Biography, TextWrapping = TextWrapping.Wrap });
        var dialog = new ContentDialog
        {
            XamlRoot = XamlRoot, Title = "选手资料", Content = panel,
            CloseButtonText = "关闭", PrimaryButtonText = "WTT 官网资料"
        };
        if (await dialog.ShowAsync() == ContentDialogResult.Primary && profile.OfficialPage is not null)
            await Windows.System.Launcher.LaunchUriAsync(profile.OfficialPage);
    }

    private async void Refresh_Click(object sender, RoutedEventArgs e)
    {
        if ((_wttDrawMode || _asianDrawMode) &&
            DrawProjectSelect.SelectedItem is string project)
        {
            _drawCancellation?.Cancel();
            var request = new CancellationTokenSource();
            _drawCancellation = request;
            var previousStage = (DrawStageSelect.SelectedItem as DrawStage)?.Code;
            if (_wttDrawMode && DrawEventSelect.SelectedItem is DrawEvent selected)
                await ViewModel.LoadWttDrawAsync(selected.Id, project, request.Token);
            else if (_asianDrawMode)
                await ViewModel.LoadAsianDrawAsync(project, request.Token);
            if (request.IsCancellationRequested) return;
            var stage = ViewModel.WttStages.FirstOrDefault(s => s.Code == previousStage) ??
                ViewModel.WttStages.FirstOrDefault();
            DrawStageSelect.SelectedItem = stage;
            ViewModel.SelectDrawStage(stage);
            RenderBracket();
        }
        else ViewModel.Refresh();
    }

    private void MiniScore_Click(object sender, RoutedEventArgs e)
    {
        if (_miniWindow is not null) { _miniWindow.Activate(); return; }
        var mini = new MiniScoreWindow(ViewModel);
        _miniWindow = mini;
        mini.Closed += (_, _) => _miniWindow = null;
        mini.DetailRequested += id =>
        {
            if (ViewModel.MiniCandidates.FirstOrDefault(item => item.Id == id) is not { } item)
                return;
            _returnSection = Navigation.SelectedItem is NavigationViewItem nav &&
                nav.Tag is string tag ? tag : "home";
            OpenMatchDetail(item);
            ((App)Application.Current).MainWindow?.Activate();
        };
        mini.Activate();
    }

    private void MatchList_ItemClick(object sender, ItemClickEventArgs e)
    {
        if (e.ClickedItem is not MatchItemViewModel item) return;
        _returnSection = Navigation.SelectedItem is NavigationViewItem nav && nav.Tag is string tag
            ? tag : "home";
        OpenMatchDetail(item);
    }

    private void ScoreBreakdown_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: MatchItemViewModel item }) return;
        _returnSection = Navigation.SelectedItem is NavigationViewItem nav &&
            nav.Tag is string tag ? tag : "home";
        OpenMatchDetail(item);
    }

    private async void OpenMatchDetail(MatchItemViewModel item)
    {
        SettingsView.Visibility = Visibility.Collapsed;
        MatchList.Visibility = Visibility.Collapsed;
        DrawsView.Visibility = Visibility.Collapsed;
        RankingsView.Visibility = Visibility.Collapsed;
        if (_observedDetail is not null) _observedDetail.PropertyChanged -= DetailItem_PropertyChanged;
        _observedDetail = item;
        item.PropertyChanged += DetailItem_PropertyChanged;
        _lastDetailScore = item.Score;
        _renderedTrend.Clear();
        TrendCanvas.Children.Clear();
        _trendGuide = null;
        ViewModel.OpenDetail(item.Id);
        _detailCancellation?.Cancel();
        _detailCancellation = new CancellationTokenSource();
        _ = LoadMatchPortraitAsync(item, true, _detailCancellation.Token);
        _ = LoadMatchPortraitAsync(item, false, _detailCancellation.Token);
        try { await ViewModel.LoadDetailAsync(item.Id, _detailCancellation.Token); }
        catch (OperationCanceledException) { }
        catch (Exception error)
        {
            if (ViewModel.IsDetail && ViewModel.Selected?.Id == item.Id)
                await new ContentDialog
                {
                    XamlRoot = XamlRoot, Title = "比赛详情暂不可用",
                    Content = $"比分卡片仍可查看，官方详情暂时无法加载：{error.Message}",
                    CloseButtonText = "关闭"
                }.ShowAsync();
        }
    }

    private async Task LoadMatchPortraitAsync(MatchItemViewModel item, bool first,
        CancellationToken ct)
    {
        var match = item.Match;
        if (item.IsClubFixture) return;
        var raw = first ? match.PlayerARaw : match.PlayerBRaw;
        var names = raw.Contains('/') ? raw.Split('/', StringSplitOptions.TrimEntries |
            StringSplitOptions.RemoveEmptyEntries) : [raw.Length > 0 ? raw :
                first ? match.PlayerA : match.PlayerB];
        if (names.Length == 0) return;
        var country = first ? match.PlayerACountryCode : match.PlayerBCountryCode;
        try
        {
            for (var index = 0; index < Math.Min(names.Length, 2); index++)
            {
                var suppliedId = names.Length == 1
                    ? first ? match.PlayerAId : match.PlayerBId : "";
                var uri = await ViewModel.GetMatchPortraitAsync(names[index], names[index],
                    suppliedId, country, ct);
                if (ct.IsCancellationRequested || ViewModel.Selected?.Id != item.Id) return;
                if (uri is null) continue;
                if (first)
                {
                    if (index == 0) item.PlayerAPortraitUri = uri.ToString();
                    else item.PlayerASecondPortraitUri = uri.ToString();
                }
                else
                {
                    if (index == 0) item.PlayerBPortraitUri = uri.ToString();
                    else item.PlayerBSecondPortraitUri = uri.ToString();
                }
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { }
        catch { /* The portrait is optional; the score and controls remain available. */ }
    }

    private void Back_Click(object sender, RoutedEventArgs e)
    {
        _detailCancellation?.Cancel();
        if (_observedDetail is not null) _observedDetail.PropertyChanged -= DetailItem_PropertyChanged;
        _observedDetail = null;
        ViewModel.SelectSection(_returnSection);
    }

    private void DetailItem_PropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(MatchItemViewModel.Score) && ViewModel.IsDetail)
        {
            var latest = _observedDetail?.Score ?? "";
            DetailScore.Text = latest;
            MotionSystem.ScoreChange(DetailOldScore, DetailScore, _lastDetailScore, latest);
            _lastDetailScore = latest;
        }
    }

    private void RenderTrend(IReadOnlyList<TrendPoint> points)
    {
        var positioned = new List<(TrendPoint Point, double X, double Y)>();
        var offset = 0;
        var previousSet = 0;
        var previousMaximum = 0;
        foreach (var point in points)
        {
            if (previousSet != 0 && point.SetNumber != previousSet)
            {
                offset += previousMaximum + 4;
                previousMaximum = 0;
            }
            previousSet = point.SetNumber;
            previousMaximum = Math.Max(previousMaximum, point.Progress);
            positioned.Add((point, 28 + 10.0 * (offset + point.Progress),
                105 - 8.0 * Math.Clamp(point.Difference, -11, 11)));
        }
        var append = _renderedTrend.Count <= positioned.Count &&
            _renderedTrend.Select((old, index) =>
                old.Point.SetNumber == positioned[index].Point.SetNumber &&
                old.Point.ScoreA == positioned[index].Point.ScoreA &&
                old.Point.ScoreB == positioned[index].Point.ScoreB &&
                old.X == positioned[index].X && old.Y == positioned[index].Y).All(equal => equal);
        if (!append)
        {
            TrendCanvas.Children.Clear();
            _renderedTrend.Clear();
            _trendGuide = null;
        }
        TrendCanvas.Width = Math.Max(640, positioned.LastOrDefault().X + 36);
        if (TrendCanvas.Children.Count == 0)
        {
            TrendCanvas.Children.Add(new Line
            {
                X1 = 0, X2 = TrendCanvas.Width, Y1 = 105, Y2 = 105,
                Stroke = new SolidColorBrush(Windows.UI.Color.FromArgb(90, 110, 130, 150)),
                StrokeThickness = 1
            });
        }
        else if (TrendCanvas.Children[0] is Line baseline) baseline.X2 = TrendCanvas.Width;
        for (var index = _renderedTrend.Count; index < positioned.Count; index++)
        {
            var sample = positioned[index];
            if (index > 0 && positioned[index - 1].Point.SetNumber == sample.Point.SetNumber)
                TrendCanvas.Children.Add(new Line
                {
                    X1 = positioned[index - 1].X, Y1 = positioned[index - 1].Y,
                    X2 = sample.X, Y2 = sample.Y,
                    Stroke = new SolidColorBrush(Windows.UI.Color.FromArgb(255, 37, 99, 235)),
                    StrokeThickness = 2.5
                });
            var dot = new Ellipse
            {
                Width = sample.Point.Final ? 9 : 6,
                Height = sample.Point.Final ? 9 : 6,
                Fill = new SolidColorBrush(Windows.UI.Color.FromArgb(255, 37, 99, 235))
            };
            Canvas.SetLeft(dot, sample.X - dot.Width / 2);
            Canvas.SetTop(dot, sample.Y - dot.Height / 2);
            TrendCanvas.Children.Add(dot);
            MotionSystem.Enter(dot);
        }
        _renderedTrend.Clear();
        _renderedTrend.AddRange(positioned);
        TrendHint.Text = points.Count == 0 ? "暂无可观察的局分" :
            $"已记录 {points.Count} 个官方或轮询观察点";
    }

    private void TrendCanvas_PointerMoved(object sender, PointerRoutedEventArgs e)
    {
        if (_renderedTrend.Count == 0) return;
        var x = e.GetCurrentPoint(TrendCanvas).Position.X;
        var nearest = _renderedTrend.MinBy(p => Math.Abs(p.X - x));
        TrendHint.Text = $"第{nearest.Point.SetNumber}局 {nearest.Point.ScoreA}:{nearest.Point.ScoreB}" +
            $" · 分差 {nearest.Point.Difference:+#;-#;0}";
        if (_trendGuide is null)
        {
            _trendGuide = new Line
            {
                Y1 = 8, Y2 = 202, StrokeThickness = 1,
                Stroke = new SolidColorBrush(Windows.UI.Color.FromArgb(150, 100, 116, 139))
            };
            TrendCanvas.Children.Add(_trendGuide);
        }
        _trendGuide.X1 = _trendGuide.X2 = nearest.X;
    }

    private void TrendCanvas_PointerExited(object sender, PointerRoutedEventArgs e)
    {
        if (_trendGuide is not null)
        {
            TrendCanvas.Children.Remove(_trendGuide);
            _trendGuide = null;
        }
        TrendHint.Text = _renderedTrend.Count == 0 ? "暂无可观察的局分" :
            $"已记录 {_renderedTrend.Count} 个官方或轮询观察点";
    }

    private void Favorite_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button button && button.Tag is string id)
            ViewModel.ToggleFavorite(id);
    }

    private async void CalendarExport_Click(object sender, RoutedEventArgs e)
    {
        if (ViewModel.Selected?.Match is not { Status: MatchStatus.Upcoming } match ||
            ((App)Application.Current).MainWindow is not { } window) return;
        try
        {
            var picker = new FileSavePicker(window.AppWindow.Id)
            {
                SuggestedFileName = "乒乓球比赛-" + match.StartTime.ToString("yyyyMMdd-HHmm"),
                DefaultFileExtension = ".ics",
                SuggestedStartLocation = PickerLocationId.DocumentsLibrary
            };
            picker.FileTypeChoices.Add("日历文件", new List<string> { ".ics" });
            var result = await picker.PickSaveFileAsync();
            if (result is null) return;
            await File.WriteAllBytesAsync(result.Path, CalendarExport.Build(match));
        }
        catch (Exception error)
        {
            await new ContentDialog
            {
                XamlRoot = XamlRoot, Title = "日历导出失败", Content = error.Message,
                CloseButtonText = "关闭"
            }.ShowAsync();
        }
    }

    private void MatchCard_PointerEntered(object sender, PointerRoutedEventArgs e)
    {
        if (sender is UIElement element) MotionSystem.Hover(element, true);
    }

    private void MatchCard_PointerExited(object sender, PointerRoutedEventArgs e)
    {
        if (sender is UIElement element) MotionSystem.Hover(element, false);
    }

    private async void Account_Click(object sender, RoutedEventArgs e)
    {
        using var cancellation = new CancellationTokenSource();
        var status = new TextBlock { Text = ViewModel.CloudStatus, TextWrapping = TextWrapping.Wrap };
        var projectUrl = new TextBox { Header = "Supabase 项目地址",
            PlaceholderText = "https://项目编号.supabase.co" };
        var publicKey = new PasswordBox { Header = "公开 anon / publishable key" };
        var configure = new Button { Content = "连接项目" };
        var email = new TextBox { Header = "邮箱", PlaceholderText = "name@example.com" };
        var password = new PasswordBox { Header = "密码" };
        var signIn = new Button { Content = "登录" };
        var signUp = new Button { Content = "注册新账号" };
        var signOut = new Button { Content = "退出当前账号" };
        var configBox = new StackPanel { Spacing = 10 };
        configBox.Children.Add(projectUrl);
        configBox.Children.Add(publicKey);
        configBox.Children.Add(configure);
        var loginActions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10 };
        loginActions.Children.Add(signIn);
        loginActions.Children.Add(signUp);
        var loginBox = new StackPanel { Spacing = 10 };
        loginBox.Children.Add(email);
        loginBox.Children.Add(password);
        loginBox.Children.Add(loginActions);
        var body = new StackPanel { Spacing = 16, Width = 440 };
        body.Children.Add(status);
        body.Children.Add(configBox);
        body.Children.Add(loginBox);
        body.Children.Add(signOut);
        body.Children.Add(new TextBlock
        {
            Text = "未登录时关注保存在本机。登录后合并到该账号；断网修改会在恢复连接后同步。密码不会保存。",
            TextWrapping = TextWrapping.Wrap, Opacity = 0.65
        });
        void Update()
        {
            status.Text = ViewModel.CloudStatus;
            configBox.Visibility = ViewModel.CloudConfigured ? Visibility.Collapsed : Visibility.Visible;
            loginBox.Visibility = ViewModel.CloudConfigured && !ViewModel.CloudSignedIn
                ? Visibility.Visible : Visibility.Collapsed;
            signOut.Visibility = ViewModel.CloudSignedIn ? Visibility.Visible : Visibility.Collapsed;
        }
        configure.Click += (_, _) =>
        {
            try
            {
                ViewModel.ConfigureCloud(projectUrl.Text, publicKey.Password);
                publicKey.Password = "";
            }
            catch (Exception error) when (error is ArgumentException or IOException)
            { status.Text = error.Message; return; }
            Update();
        };
        async Task Authenticate(bool register)
        {
            signIn.IsEnabled = signUp.IsEnabled = false;
            await ViewModel.CloudSignInAsync(email.Text, password.Password,
                register, cancellation.Token);
            password.Password = "";
            signIn.IsEnabled = signUp.IsEnabled = true;
            Update();
        }
        signIn.Click += async (_, _) => await Authenticate(false);
        signUp.Click += async (_, _) => await Authenticate(true);
        signOut.Click += async (_, _) =>
        {
            try { await ViewModel.CloudSignOutAsync(cancellation.Token); }
            catch (OperationCanceledException) { }
            Update();
        };
        var dialog = new ContentDialog
        {
            Title = "账号与云端关注", Content = body, CloseButtonText = "关闭", XamlRoot = XamlRoot
        };
        dialog.Closed += (_, _) => cancellation.Cancel();
        Update();
        await dialog.ShowAsync();
    }

}
