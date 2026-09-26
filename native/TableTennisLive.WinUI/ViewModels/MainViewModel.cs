using System.Collections.ObjectModel;
using System.ComponentModel;
using Microsoft.UI.Dispatching;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Services;
using TableTennisLive.Core.Sources;

namespace TableTennisLive_WinUI.ViewModels;

public sealed class MainViewModel : INotifyPropertyChanged, IAsyncDisposable
{
    private readonly DispatcherQueue _dispatcher;
    private readonly FavoriteStore _favorites = new();
    private readonly CloudSyncService _cloud;
    private readonly CancellationTokenSource _cloudStop = new();
    private readonly Task _cloudLoop;
    private readonly ScoreTrendStore _trends = new();
    private readonly MatchAlertTracker _alertTracker = new();
    private readonly AlertSettings _alertSettings = new();
    private readonly RankingService _rankings = new();
    private readonly PlayerProfileService _profiles = new();
    private readonly SemaphoreSlim _portraitSlots = new(4);
    private readonly Dictionary<string, string> _portraitCache = [];
    private readonly HashSet<string> _portraitLoading = [];
    private readonly WttDrawService _wttDraws = new();
    private readonly AsianGamesDrawService _asianDraws = new();
    private readonly CancellationTokenSource _rankingStop = new();
    private readonly Task _rankingLoop;
    private readonly MatchRefreshService _refresh;
    private readonly Dictionary<string, MatchItemViewModel> _all = [];
    private string _section = "home";
    private string _query = "";
    private string _source = "";
    private string _health = "正在连接官方数据源…";
    private MatchItemViewModel? _selected;
    private string _rankingEvent = "MS";
    private string _rankingCategory = "SEN";
    private string _rankingHealth = "正在读取官方排名…";
    private string _drawStatus = "请选择赛事与项目";
    private string _majorCategory = "亚运会";
    private string _cloudStatus = "未登录 · 关注仅保存在此电脑";
    private IReadOnlyList<RankingEntry> _rankingSnapshot = [];
    public event PropertyChangedEventHandler? PropertyChanged;
    public event Action<IReadOnlyList<TrendPoint>>? TrendChanged;
    public event Action<MatchAlert>? AlertRaised;
    public event Action? MatchesChanged;

    public ObservableCollection<MatchItemViewModel> Matches { get; } = [];
    public IReadOnlyList<MatchItemViewModel> MiniCandidates => _all.Values
        .Where(item => item.Match.Status == MatchStatus.Live || item.IsFavorite)
        .OrderBy(item => !item.IsFavorite)
        .ThenBy(item => item.Match.Status != MatchStatus.Live)
        .ThenBy(item => item.Match.StartTime)
        .Take(40).ToArray();
    public ObservableCollection<RankingEntry> RankingRows { get; } = [];
    public ObservableCollection<DrawEvent> WttEvents { get; } = [];
    public ObservableCollection<DrawStage> WttStages { get; } = [];
    public ObservableCollection<DrawRound> DrawRounds { get; } = [];
    public string DrawStatus
    {
        get => _drawStatus;
        private set { _drawStatus = value; Changed(nameof(DrawStatus)); }
    }
    public string RankingHealth
    {
        get => _rankingHealth;
        private set { _rankingHealth = value; Changed(nameof(RankingHealth)); }
    }
    public string RankingEvent => _rankingEvent;
    public string RankingCategory => _rankingCategory;
    public bool CloudConfigured => _cloud.Configured;
    public bool CloudSignedIn => _cloud.SignedIn;
    public string CloudEmail => _cloud.Email;
    public string CloudStatus
    {
        get => _cloudStatus;
        private set { _cloudStatus = value; Changed(nameof(CloudStatus)); }
    }
    public bool IsRankings => _section == "rankings";
    public bool IsMajors => _section == "majors";
    public string MajorCategory => _majorCategory;
    public MatchItemViewModel? Selected
    {
        get => _selected;
        private set { _selected = value; Changed(nameof(Selected)); }
    }
    public string Health
    {
        get => _health;
        private set { _health = value; Changed(nameof(Health)); }
    }
    public string SectionTitle => _section switch
    {
        "live" => "实时比分", "schedule" => "今日赛程", "favorites" => "我的关注",
        "search" => "搜索结果", "detail" => "比赛详情", "wtt" => "WTT",
        "majors" => "大赛", "tleague" => "日本 T.League", "ttbl" => "德国 TTBL",
        "cttsl" => "中国乒超", "rankings" => "世界排名", _ => "赛事中心"
    };
    public bool IsDetail => _section == "detail";

    public MainViewModel(DispatcherQueue dispatcher)
    {
        _dispatcher = dispatcher;
        _cloud = new CloudSyncService(_favorites);
        _refresh = new MatchRefreshService([new AsianGamesSource(), new WttSource(),
            new TtblSource(), new TLeagueSource()]);
        foreach (var match in HistoricalMajorArchive.Load())
            _all[match.Id] = new(match, _favorites.Contains(match.Id));
        _refresh.SnapshotChanged += (changed, removed) =>
            _dispatcher.TryEnqueue(() => Apply(changed, removed));
        _refresh.HealthChanged += status => _dispatcher.TryEnqueue(() =>
            Health = status.Error is null
                ? $"{status.Name} · {status.LastSuccess:HH:mm:ss} 已更新"
                : $"{status.Name} · {status.Error} · 旧数据已保留");
        _refresh.Start();
        _rankingSnapshot = _rankings.LoadCached();
        UpdateRankingRows();
        _rankingLoop = Task.Run(() => PollRankingsAsync(_rankingStop.Token));
        _cloudLoop = RunCloudLoopAsync(_cloudStop.Token);
    }

    public void ConfigureCloud(string address, string key)
    {
        _cloud.Configure(address, key);
        CloudStatus = "云端已配置 · 请登录";
        Changed(nameof(CloudConfigured));
    }

    public async Task<bool> CloudSignInAsync(string email, string password,
        bool register, CancellationToken ct)
    {
        CloudStatus = "正在连接云端…";
        try
        {
            var signedIn = await _cloud.SignInAsync(email, password, register, ct);
            CloudStatus = signedIn
                ? _cloud.LastSyncError.Length > 0
                    ? $"账号已登录 · {_cloud.Email} · 关注同步待修复：{_cloud.LastSyncError}"
                    : $"已同步 · {_cloud.Email}"
                : "注册邮件已发送，请验证邮箱后登录";
            Changed(nameof(CloudSignedIn), nameof(CloudEmail));
            RefreshFavoriteState();
            return signedIn;
        }
        catch (Exception error) when (error is not OperationCanceledException)
        {
            CloudStatus = _cloud.SignedIn
                ? $"已登录 · {_cloud.Email} · 同步失败，稍后重试 · {error.Message}"
                : "云端连接失败 · " + error.Message;
            Changed(nameof(CloudSignedIn), nameof(CloudEmail));
            RefreshFavoriteState();
            return false;
        }
    }

    public async Task CloudSignOutAsync(CancellationToken ct)
    {
        await _cloud.SignOutAsync(ct);
        CloudStatus = "未登录 · 关注仅保存在此电脑";
        Changed(nameof(CloudSignedIn), nameof(CloudEmail));
        RefreshFavoriteState();
    }

    private async Task RunCloudLoopAsync(CancellationToken ct)
    {
        try
        {
            if (await _cloud.RestoreAsync(ct))
            {
                CloudStatus = $"已同步 · {_cloud.Email}";
                Changed(nameof(CloudSignedIn), nameof(CloudEmail));
                RefreshFavoriteState();
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { return; }
        catch (Exception error)
        {
            CloudStatus = _cloud.SignedIn
                ? $"已登录 · {_cloud.Email} · 同步待重试 · {error.Message}"
                : "云端暂不可用 · " + error.Message;
            Changed(nameof(CloudSignedIn), nameof(CloudEmail));
            RefreshFavoriteState();
        }
        while (!ct.IsCancellationRequested)
        {
            try
            {
                await Task.Delay(TimeSpan.FromSeconds(30), ct);
                if (!_cloud.SignedIn) continue;
                await _cloud.SyncAsync(ct);
                CloudStatus = $"已同步 · {_cloud.Email}";
                RefreshFavoriteState();
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { break; }
            catch (Exception error) { CloudStatus = "同步失败，稍后重试 · " + error.Message; }
        }
    }

    private async Task SyncCloudAsync()
    {
        try
        {
            await _cloud.SyncAsync(_cloudStop.Token);
            CloudStatus = $"已同步 · {_cloud.Email}";
            RefreshFavoriteState();
        }
        catch (OperationCanceledException) when (_cloudStop.IsCancellationRequested) { }
        catch (Exception error) { CloudStatus = "离线修改已保存，稍后重试 · " + error.Message; }
    }

    private void RefreshFavoriteState()
    {
        foreach (var item in _all.Values) item.SetFavorite(_favorites.Contains(item.Id));
        Refilter();
        MatchesChanged?.Invoke();
    }

    public void Refresh() => _refresh.RefreshNow();

    public void SelectSection(string section)
    {
        _section = section;
        if (section != "detail") Selected = null;
        Changed(nameof(SectionTitle), nameof(IsDetail));
        Changed(nameof(IsRankings));
        Changed(nameof(IsMajors));
        Refilter();
    }

    public void SetSource(string source)
    {
        _source = source;
        Refilter();
    }

    public void Search(string text)
    {
        _query = text.Trim().ToLowerInvariant();
        _section = _query.Length == 0 ? "home" : "search";
        Changed(nameof(SectionTitle), nameof(IsDetail));
        Changed(nameof(IsRankings));
        Changed(nameof(IsMajors));
        Refilter();
    }

    public void OpenDetail(string id)
    {
        if (!_all.TryGetValue(id, out var item)) return;
        Selected = item;
        _trends.Observe(item.Match);
        TrendChanged?.Invoke(_trends.Points(id));
        _section = "detail";
        Changed(nameof(SectionTitle), nameof(IsDetail));
        Changed(nameof(IsRankings));
        Changed(nameof(IsMajors));
    }

    public void SelectMajorCategory(string category)
    {
        if (category is not ("亚运会" or "奥运会" or "世锦赛" or "世界杯")) return;
        _majorCategory = category;
        Changed(nameof(MajorCategory));
        Refilter();
    }

    public void SelectRankingEvent(string eventCode)
    {
        if (eventCode is not ("MS" or "WS" or "MD" or "WD" or "XD" or
            "MDI" or "WDI" or "XDI")) return;
        _rankingEvent = eventCode;
        Changed(nameof(RankingEvent));
        UpdateRankingRows();
    }

    public void SelectRankingCategory(string category)
    {
        if (category is not ("SEN" or "YOU")) return;
        _rankingCategory = category;
        Changed(nameof(RankingCategory));
        UpdateRankingRows();
    }

    public async Task<PlayerProfile?> GetPlayerProfileAsync(string name, string raw,
        string country, string id, CancellationToken ct)
    {
        var resolved = PlayerProfileService.ResolveId(name, raw, country, id, _rankingSnapshot);
        if (resolved is null) return null;
        var row = _rankingSnapshot.FirstOrDefault(item => item.PlayerId == resolved &&
            item.CategoryCode == "SEN" && item.EventCode is "MS" or "WS");
        return await _profiles.GetAsync(resolved, row, ct);
    }

    public async Task<Uri?> GetMatchPortraitAsync(string displayName, string rawName,
        string suppliedId, string countryCode, CancellationToken ct)
    {
        if (displayName.Contains('/') || rawName.Contains('/')) return null;
        var country = countryCode.Length > 0 ? countryCode : CountryFlags.CodeFromName(displayName);
        var resolved = PlayerProfileService.ResolveId(displayName, rawName, country,
            suppliedId, _rankingSnapshot);
        return resolved is null ? null : await _profiles.GetPortraitAsync(resolved, ct);
    }

    public async Task EnsureRankingPortraitAsync(RankingEntry row)
    {
        if (row.IsPair || row.PlayerId.Length == 0 || row.PortraitUri.Length > 0 ||
            !_portraitLoading.Add(row.PlayerId)) return;
        try
        {
            await _portraitSlots.WaitAsync(_rankingStop.Token).ConfigureAwait(false);
            try
            {
                var portrait = await _profiles.GetPortraitAsync(row.PlayerId,
                    _rankingStop.Token).ConfigureAwait(false);
                if (portrait is null) return;
                _dispatcher.TryEnqueue(() =>
                {
                    var url = portrait.ToString();
                    _portraitCache[row.PlayerId] = url;
                    for (var index = 0; index < RankingRows.Count; index++)
                        if (!RankingRows[index].IsPair &&
                            RankingRows[index].PlayerId == row.PlayerId)
                            RankingRows[index] = RankingRows[index] with { PortraitUri = url };
                });
            }
            finally { _portraitSlots.Release(); }
        }
        catch (OperationCanceledException) when (_rankingStop.IsCancellationRequested) { }
        catch { /* An unavailable portrait keeps the neutral silhouette. */ }
        finally { _dispatcher.TryEnqueue(() => _portraitLoading.Remove(row.PlayerId)); }
    }

    public async Task LoadWttEventsAsync(CancellationToken ct)
    {
        DrawStatus = "正在读取 WTT 官方赛事…";
        try
        {
            var rows = await _wttDraws.GetEventsAsync(ct);
            WttEvents.Clear();
            foreach (var row in rows) WttEvents.Add(row);
            DrawStatus = rows.Count == 0 ? "近期没有可选择的 WTT 赛事" :
                $"{rows.Count} 个赛事 · 选择项目后加载官方签表";
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { }
        catch (Exception error) { DrawStatus = "赛事目录暂不可用 · " + error.Message; }
    }

    public async Task LoadWttDrawAsync(int eventId, string project, CancellationToken ct)
    {
        DrawStatus = "正在读取 WTT 官方签表…";
        try
        {
            var rows = await _wttDraws.GetDrawAsync(eventId, project, ct);
            WttStages.Clear();
            DrawRounds.Clear();
            foreach (var row in rows) WttStages.Add(row);
            DrawStatus = rows.Count == 0 ? "官网尚未发布此项目签表" :
                $"官方签表 · {rows.Sum(s => s.Rounds.Sum(r => r.Matches.Count))} 场 · 可缩放";
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { }
        catch (Exception error) { DrawStatus = "签表暂不可用 · " + error.Message; }
    }

    public async Task LoadAsianDrawAsync(string project, CancellationToken ct)
    {
        DrawStatus = "正在读取亚运会官方签表…";
        try
        {
            var rows = await _asianDraws.GetDrawAsync(project, ct);
            WttStages.Clear();
            DrawRounds.Clear();
            foreach (var row in rows) WttStages.Add(row);
            DrawStatus = rows.Count == 0 ? "官网尚未发布此项目签表" :
                $"亚运会官方签表 · {rows.Sum(s => s.Rounds.Sum(r => r.Matches.Count))} 场 · 可缩放";
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { }
        catch (Exception error) { DrawStatus = "亚运会签表暂不可用 · " + error.Message; }
    }

    public void SelectDrawStage(DrawStage? stage)
    {
        DrawRounds.Clear();
        if (stage is null) return;
        foreach (var row in stage.Rounds) DrawRounds.Add(row);
    }

    private async Task PollRankingsAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                var rows = await _rankings.RefreshAsync(ct).ConfigureAwait(false);
                _dispatcher.TryEnqueue(() =>
                {
                    _rankingSnapshot = rows;
                    UpdateRankingRows();
                    RankingHealth = $"WTT / ITTF 官方 · {rows.FirstOrDefault()?.Published:yyyy-MM-dd} 发布 · 每 60 秒检查";
                });
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { break; }
            catch (Exception error)
            {
                _dispatcher.TryEnqueue(() => RankingHealth =
                    $"官方排名暂不可用 · {error.Message} · 已保留缓存");
            }
            _dispatcher.TryEnqueue(CheckDueAlerts);
            try { await Task.Delay(TimeSpan.FromSeconds(60), ct).ConfigureAwait(false); }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { break; }
        }
    }

    private void UpdateRankingRows()
    {
        var wanted = _rankingSnapshot.Where(r => r.CategoryCode == _rankingCategory &&
            r.EventCode == _rankingEvent).ToArray();
        RankingRows.Clear();
        foreach (var row in wanted) RankingRows.Add(!row.IsPair &&
            _portraitCache.TryGetValue(row.PlayerId, out var portrait)
                ? row with { PortraitUri = portrait } : row);
    }

    public async Task LoadDetailAsync(string id, CancellationToken ct)
    {
        var detail = await _refresh.GetDetailAsync(id, ct).ConfigureAwait(false);
        if (detail is not null) _dispatcher.TryEnqueue(() =>
        {
            if (_all.TryGetValue(id, out var item)) item.Update(detail);
        });
    }

    public void ToggleFavorite(string id)
    {
        var enabled = _favorites.Toggle(id);
        if (_all.TryGetValue(id, out var item)) item.SetFavorite(enabled);
        if (!enabled) _alertTracker.Forget(id);
        else if (_all.TryGetValue(id, out item))
            _alertTracker.Update(item.Match, true, _alertSettings.Enabled);
        if (_section == "favorites") Refilter();
        MatchesChanged?.Invoke();
        if (_cloud.SignedIn) _ = SyncCloudAsync();
    }

    public bool AlertEnabled(string kind) => _alertSettings.Enabled(kind);
    public void SetAlert(string kind, bool enabled) => _alertSettings.Set(kind, enabled);

    private void CheckDueAlerts()
    {
        var now = DateTimeOffset.Now;
        foreach (var item in _all.Values.Where(x => x.IsFavorite))
        {
            var alert = _alertTracker.Due(item.Match, now, _alertSettings.Enabled);
            if (alert is not null) AlertRaised?.Invoke(alert);
        }
    }

    private void Apply(IReadOnlyList<Match> changed, IReadOnlyList<string> removed)
    {
        foreach (var id in removed) { _all.Remove(id); _alertTracker.Forget(id); }
        foreach (var match in changed)
        {
            foreach (var alert in _alertTracker.Update(match, _favorites.Contains(match.Id),
                _alertSettings.Enabled)) AlertRaised?.Invoke(alert);
            if (_all.TryGetValue(match.Id, out var item)) item.Update(match);
            else _all[match.Id] = new(match, _favorites.Contains(match.Id));
            _trends.Observe(match);
            if (Selected?.Id == match.Id) TrendChanged?.Invoke(_trends.Points(match.Id));
        }
        Refilter();
        CheckDueAlerts();
        MatchesChanged?.Invoke();
    }

    private void Refilter()
    {
        if (IsDetail) return;
        var now = DateTimeOffset.Now;
        var rows = _all.Values.Where(item => _section switch
        {
            "live" => item.Match.Status == MatchStatus.Live,
            "schedule" => item.Match.Status != MatchStatus.Live &&
                item.Match.StartTime.Date == now.Date,
            "favorites" => item.IsFavorite,
            "search" => _query.Length > 0 && item.Match.SearchText.Contains(_query),
            "wtt" => item.Match.Source == "WTT",
            "majors" => _majorCategory == "亚运会"
                ? item.Match.Source == "majors"
                : item.Match.Source == "historical" &&
                  (_majorCategory == "世锦赛"
                      ? item.Match.MajorCategory.Contains("世锦赛")
                      : _majorCategory == "世界杯"
                          ? item.Match.MajorCategory.Contains("世界杯")
                          : item.Match.MajorCategory == "奥运会"),
            "tleague" => item.Match.Source == "T.League",
            "ttbl" => item.Match.Source == "TTBL",
            "cttsl" => false,
            _ => item.Match.Status != MatchStatus.Finished ||
                item.Match.StartTime >= now.AddHours(-72)
        });
        if (_source.Length > 0) rows = rows.Where(item => item.Match.Source == _source);
        var ordered = rows.OrderBy(item => item.Match.Status == MatchStatus.Live ? 0 :
                item.Match.Status == MatchStatus.Upcoming ? 1 : 2)
            .ThenBy(item => item.Match.Status == MatchStatus.Finished
                ? -item.Match.StartTime.ToUnixTimeSeconds() : item.Match.StartTime.ToUnixTimeSeconds())
            .ToArray();
        // Incremental collection reconciliation: unchanged cards retain their XAML visuals.
        var wanted = ordered.ToHashSet();
        for (var i = Matches.Count - 1; i >= 0; i--)
            if (!wanted.Contains(Matches[i])) Matches.RemoveAt(i);
        for (var i = 0; i < ordered.Length; i++)
        {
            if (i < Matches.Count && ReferenceEquals(Matches[i], ordered[i])) continue;
            var existing = Matches.IndexOf(ordered[i]);
            if (existing >= 0) Matches.Move(existing, i);
            else Matches.Insert(i, ordered[i]);
        }
    }

    private void Changed(params string[] properties)
    {
        foreach (var property in properties)
            PropertyChanged?.Invoke(this, new(property));
    }

    public async ValueTask DisposeAsync()
    {
        _rankingStop.Cancel();
        _cloudStop.Cancel();
        await _refresh.DisposeAsync();
        try { await _rankingLoop; }
        catch (OperationCanceledException) { }
        try { await _cloudLoop; }
        catch (OperationCanceledException) { }
        _rankingStop.Dispose();
        _cloudStop.Dispose();
        _cloud.Dispose();
        _rankings.Dispose();
        _profiles.Dispose();
        _wttDraws.Dispose();
        _asianDraws.Dispose();
    }
}
