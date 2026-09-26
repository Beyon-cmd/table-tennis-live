using System.ComponentModel;
using System.Runtime.CompilerServices;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Services;
using Microsoft.UI.Xaml;

namespace TableTennisLive_WinUI.ViewModels;

public sealed record TeamGameItem(string PlayerA, string PlayerB, string Score,
    string Sets, IReadOnlyList<SetColumn> SetColumns);

public sealed record SetColumn(string Label, int Left, int Right, bool IsCurrent);

public sealed class MatchItemViewModel : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;
    private Match _match;
    private bool _favorite;
    private string _playerAPortraitUri = "";
    private string _playerBPortraitUri = "";
    private string _playerASecondPortraitUri = "";
    private string _playerBSecondPortraitUri = "";

    public MatchItemViewModel(Match match, bool favorite)
    {
        _match = match;
        _favorite = favorite;
    }

    public Match Match => _match;
    public string Id => _match.Id;
    public string Competition => _match.Competition;
    public string PlayerA => ChineseNames.Display(_match.PlayerA);
    public string PlayerB => ChineseNames.Display(_match.PlayerB);
    public string PlayerAWithFlag => CountryFlags.WithoutCode(PlayerA);
    public string PlayerBWithFlag => CountryFlags.WithoutCode(PlayerB);
    public string PlayerAFlagUri => CountryFlags.AssetUri(_match.PlayerACountryCode.Length == 3
        ? _match.PlayerACountryCode.ToUpperInvariant() : CountryFlags.CodeFromName(_match.PlayerA));
    public string PlayerBFlagUri => CountryFlags.AssetUri(_match.PlayerBCountryCode.Length == 3
        ? _match.PlayerBCountryCode.ToUpperInvariant() : CountryFlags.CodeFromName(_match.PlayerB));
    public string PlayerAPortraitUri
    {
        get => _playerAPortraitUri;
        set { if (_playerAPortraitUri != value) { _playerAPortraitUri = value;
            Notify(nameof(PlayerAPortraitUri), nameof(PlayerAPortraitPlaceholderVisibility),
                nameof(PlayerAPortraitAreaVisibility)); } }
    }
    public string PlayerBPortraitUri
    {
        get => _playerBPortraitUri;
        set { if (_playerBPortraitUri != value) { _playerBPortraitUri = value;
            Notify(nameof(PlayerBPortraitUri), nameof(PlayerBPortraitPlaceholderVisibility),
                nameof(PlayerBPortraitAreaVisibility)); } }
    }
    public string PlayerASecondPortraitUri
    {
        get => _playerASecondPortraitUri;
        set { if (_playerASecondPortraitUri != value) { _playerASecondPortraitUri = value;
            Notify(nameof(PlayerASecondPortraitUri), nameof(PlayerASecondPortraitVisibility),
                nameof(PlayerAPortraitPlaceholderVisibility)); } }
    }
    public string PlayerBSecondPortraitUri
    {
        get => _playerBSecondPortraitUri;
        set { if (_playerBSecondPortraitUri != value) { _playerBSecondPortraitUri = value;
            Notify(nameof(PlayerBSecondPortraitUri), nameof(PlayerBSecondPortraitVisibility),
                nameof(PlayerBPortraitPlaceholderVisibility)); } }
    }
    public Visibility PlayerASecondPortraitVisibility => IsPlayerADoubles &&
        _playerASecondPortraitUri.Length > 0 ? Visibility.Visible : Visibility.Collapsed;
    public Visibility PlayerBSecondPortraitVisibility => IsPlayerBDoubles &&
        _playerBSecondPortraitUri.Length > 0 ? Visibility.Visible : Visibility.Collapsed;
    public bool IsPlayerADoubles => _match.PlayerARaw.Contains('/');
    public bool IsPlayerBDoubles => _match.PlayerBRaw.Contains('/');
    public double PlayerAPortraitWidth => IsPlayerADoubles ? 232 : 196;
    public double PlayerBPortraitWidth => IsPlayerBDoubles ? 232 : 196;
    public double PlayerAPortraitImageWidth => IsPlayerADoubles ? 142 : 196;
    public double PlayerBPortraitImageWidth => IsPlayerBDoubles ? 142 : 196;
    public Visibility PlayerAPortraitPlaceholderVisibility =>
        _playerAPortraitUri.Length == 0 && _playerASecondPortraitUri.Length == 0
            ? Visibility.Visible : Visibility.Collapsed;
    public Visibility PlayerBPortraitPlaceholderVisibility =>
        _playerBPortraitUri.Length == 0 && _playerBSecondPortraitUri.Length == 0
            ? Visibility.Visible : Visibility.Collapsed;
    public bool IsClubFixture => _match.Source is "T.League" or "TTBL" ||
        _match.Competition.Contains("团体");
    public Visibility ClubHeaderVisibility => IsClubFixture ? Visibility.Visible : Visibility.Collapsed;
    public Visibility PlayerHeaderVisibility => IsClubFixture ? Visibility.Collapsed : Visibility.Visible;
    public Visibility PlayerAPortraitAreaVisibility => IsClubFixture &&
        _playerAPortraitUri.Length == 0 ? Visibility.Collapsed : Visibility.Visible;
    public Visibility PlayerBPortraitAreaVisibility => IsClubFixture &&
        _playerBPortraitUri.Length == 0 ? Visibility.Collapsed : Visibility.Visible;
    public Visibility PlayerAFlagVisibility => PlayerAFlagUri.Length > 0 ? Visibility.Visible : Visibility.Collapsed;
    public Visibility PlayerBFlagVisibility => PlayerBFlagUri.Length > 0 ? Visibility.Visible : Visibility.Collapsed;
    public string DisplayLabel => $"{PlayerA} vs {PlayerB}";
    public string Score => _match.Status == MatchStatus.Upcoming
        ? _match.StartTime.ToString("HH:mm")
        : _match.ScoreKnown ? $"{_match.ScoreA} : {_match.ScoreB}" : "—";
    public string Status => _match.DataStale ? "旧数据" : _match.Status switch
    {
        MatchStatus.Live => "● LIVE", MatchStatus.Finished => "已结束", _ => "即将开始"
    };
    public string Sets => string.Join("   ",
        _match.Sets.Select((set, index) => $"第{index + 1}局 {set.Left}:{set.Right}")
            .Concat(_match.CurrentSet is { } live
                ? [$"本局 {live.Left}:{live.Right}"] : []));
    public IReadOnlyList<SetColumn> SetColumns => _match.Sets
        .Select((set, index) => new SetColumn($"第 {index + 1} 局", set.Left, set.Right, false))
        .Concat(_match.CurrentSet is { } current
            ? [new SetColumn("本局", current.Left, current.Right, true)] : [])
        .ToArray();
    public string ScoreSectionTitle => _match.Games.Count > 0 || _match.Competition.Contains("团体")
        ? "团体场次结果" : "逐局比分";
    public string SetScoreNote => _match.Games.Count > 0
        ? "团体总比分在上方；下方逐场列出对阵、单场结果和每局比分" :
        SetColumns.Count > 0 ? "上行为第一位选手，下行为第二位选手" :
        _match.Status == MatchStatus.Upcoming ? "比赛尚未开始" :
        "目前未获取到逐局比分；不会根据总比分推测每局得分";
    public string TeamGamesNote => _match.Games.Count > 0 ? "" :
        _match.Competition.Contains("团体") ? "目前未获取到单场对阵与逐局结果" : "";
    public string FavoriteGlyph => _favorite ? "★" : "☆";
    public IReadOnlyList<TeamGameItem> TeamGames => _match.Games.Select(game =>
        new TeamGameItem(ChineseNames.Display(game.PlayerA), ChineseNames.Display(game.PlayerB),
            $"{game.ScoreA} : {game.ScoreB}",
            string.Join("   ", game.Sets.Select((set, index) =>
                $"第{index + 1}局 {set.Left}:{set.Right}")),
            game.Sets.Select((set, index) => new SetColumn($"第 {index + 1} 局",
                set.Left, set.Right, false)).ToArray())).ToArray();
    public bool IsFavorite => _favorite;
    public bool IsUpcoming => _match.Status == MatchStatus.Upcoming;

    public void Update(Match match)
    {
        var oldScore = Score;
        _match = match;
        Notify(nameof(Match), nameof(Competition), nameof(PlayerA), nameof(PlayerB),
            nameof(PlayerAWithFlag), nameof(PlayerBWithFlag), nameof(PlayerAFlagUri),
            nameof(PlayerBFlagUri), nameof(PlayerAFlagVisibility),
            nameof(PlayerBFlagVisibility), nameof(DisplayLabel),
            nameof(Status), nameof(Sets), nameof(SetColumns), nameof(ScoreSectionTitle),
            nameof(SetScoreNote),
            nameof(TeamGames), nameof(TeamGamesNote), nameof(IsUpcoming));
        Notify(nameof(PlayerAPortraitAreaVisibility), nameof(PlayerBPortraitAreaVisibility));
        Notify(nameof(IsClubFixture), nameof(ClubHeaderVisibility), nameof(PlayerHeaderVisibility),
            nameof(IsPlayerADoubles), nameof(IsPlayerBDoubles),
            nameof(PlayerAPortraitWidth), nameof(PlayerBPortraitWidth),
            nameof(PlayerAPortraitImageWidth), nameof(PlayerBPortraitImageWidth),
            nameof(PlayerASecondPortraitVisibility), nameof(PlayerBSecondPortraitVisibility));
        if (oldScore != Score) Notify(nameof(Score));
    }

    public void SetFavorite(bool value)
    {
        if (_favorite == value) return;
        _favorite = value;
        Notify(nameof(IsFavorite), nameof(FavoriteGlyph));
    }

    private void Notify(params string[] names)
    {
        foreach (var name in names) PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
    }
}
