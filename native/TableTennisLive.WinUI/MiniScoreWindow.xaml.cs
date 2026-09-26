using System.Collections.ObjectModel;
using System.ComponentModel;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using TableTennisLive_WinUI.ViewModels;

namespace TableTennisLive_WinUI;

public sealed partial class MiniScoreWindow : Window, INotifyPropertyChanged
{
    private readonly MainViewModel _main;
    private MatchItemViewModel? _selected;
    public event PropertyChangedEventHandler? PropertyChanged;
    public event Action<string>? DetailRequested;
    public ObservableCollection<MatchItemViewModel> Candidates { get; } = [];
    public MatchItemViewModel? Selected
    {
        get => _selected;
        private set
        {
            _selected = value;
            PropertyChanged?.Invoke(this, new(nameof(Selected)));
        }
    }

    public MiniScoreWindow(MainViewModel main)
    {
        InitializeComponent();
        _main = main;
        Root.DataContext = this;
        AppWindow.Resize(new Windows.Graphics.SizeInt32(700, 500));
        if (AppWindow.Presenter is OverlappedPresenter presenter)
            presenter.IsAlwaysOnTop = true;
        _main.MatchesChanged += UpdateMatches;
        Closed += (_, _) => _main.MatchesChanged -= UpdateMatches;
        UpdateMatches();
    }

    private void UpdateMatches()
    {
        var selectedId = Selected?.Id;
        var wanted = _main.MiniCandidates;
        for (var index = Candidates.Count - 1; index >= 0; index--)
            if (!wanted.Contains(Candidates[index])) Candidates.RemoveAt(index);
        for (var index = 0; index < wanted.Count; index++)
        {
            var existing = Candidates.IndexOf(wanted[index]);
            if (existing < 0) Candidates.Insert(index, wanted[index]);
            else if (existing != index) Candidates.Move(existing, index);
        }
        var selected = wanted.FirstOrDefault(item => item.Id == selectedId) ??
            wanted.FirstOrDefault();
        if (!ReferenceEquals(MatchSelect.SelectedItem, selected))
            MatchSelect.SelectedItem = selected;
        Selected = selected;
    }

    private void MatchSelect_SelectionChanged(object sender, SelectionChangedEventArgs e) =>
        Selected = MatchSelect.SelectedItem as MatchItemViewModel;

    private void OpenDetail_Click(object sender, RoutedEventArgs e)
    {
        if (Selected is not null) DetailRequested?.Invoke(Selected.Id);
    }
}
