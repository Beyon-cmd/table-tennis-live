using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

/// <summary>
/// One independent asynchronous loop per source. Failed polls retain the last
/// snapshot as stale; a successful response re-synchronizes it immediately.
/// UI subscribers must dispatch events onto their own UI thread.
/// </summary>
public sealed class MatchRefreshService : IAsyncDisposable
{
    private readonly IReadOnlyList<IMatchSource> _sources;
    private readonly Dictionary<string, IReadOnlyList<Match>> _bySource = [];
    private readonly Dictionary<string, SemaphoreSlim> _wakes = [];
    private readonly Dictionary<string, string> _fingerprints = [];
    private readonly CancellationTokenSource _stop = new();
    private readonly object _gate = new();
    private readonly List<Task> _loops = [];
    private bool _started;

    public event Action<IReadOnlyList<Match>, IReadOnlyList<string>>? SnapshotChanged;
    public event Action<SourceHealth>? HealthChanged;

    public MatchRefreshService(IEnumerable<IMatchSource> sources)
    {
        _sources = sources.ToArray();
        foreach (var source in _sources)
        {
            if (_wakes.ContainsKey(source.Name))
                throw new ArgumentException($"Duplicate source: {source.Name}");
            _wakes[source.Name] = new SemaphoreSlim(0, 1);
            _bySource[source.Name] = [];
        }
    }

    public IReadOnlyList<Match> Current
    {
        get { lock (_gate) return _bySource.Values.SelectMany(x => x).ToArray(); }
    }

    public void Start()
    {
        if (_started) return;
        _started = true;
        foreach (var source in _sources)
            _loops.Add(Task.Run(() => RunSourceAsync(source, _stop.Token)));
    }

    public void RefreshNow()
    {
        foreach (var wake in _wakes.Values)
            if (wake.CurrentCount == 0) wake.Release();
    }

    public async Task<Match?> GetDetailAsync(string id, CancellationToken cancellationToken)
    {
        Match? known = Current.FirstOrDefault(m => m.Id == id);
        if (known is null) return null;
        var source = _sources.FirstOrDefault(s => s.Name == known.Source);
        return source is null ? null : await source.GetDetailAsync(id, cancellationToken)
            .ConfigureAwait(false);
    }

    private async Task RunSourceAsync(IMatchSource source, CancellationToken cancellationToken)
    {
        var backoff = TimeSpan.FromSeconds(1);
        DateTimeOffset? lastSuccess = null;
        while (!cancellationToken.IsCancellationRequested)
        {
            TimeSpan next;
            try
            {
                var rows = await source.GetMatchesAsync(cancellationToken).ConfigureAwait(false);
                var stale = rows.Any(row => row.DataStale);
                if (!stale) lastSuccess = DateTimeOffset.Now;
                Apply(source.Name, rows);
                HealthChanged?.Invoke(new(source.Name, lastSuccess,
                    stale ? "部分结果沿用缓存" : null, stale));
                next = rows.Any(m => m.Status == MatchStatus.Live) ? TimeSpan.FromSeconds(2)
                    : rows.Any(m => m.Status == MatchStatus.Upcoming) ? TimeSpan.FromSeconds(10)
                    : TimeSpan.FromSeconds(15);
                backoff = TimeSpan.FromSeconds(1);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                IReadOnlyList<Match> old;
                lock (_gate) old = _bySource[source.Name];
                Apply(source.Name, old.Select(m => m with { DataStale = true }).ToArray());
                HealthChanged?.Invoke(new(source.Name, lastSuccess, ex.Message, true));
                next = backoff;
                backoff = TimeSpan.FromSeconds(Math.Min(backoff.TotalSeconds * 2, 30));
            }
            try
            {
                await _wakes[source.Name].WaitAsync(next, cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
        }
    }

    private void Apply(string sourceName, IReadOnlyList<Match> rows)
    {
        Match[] changed;
        string[] removed;
        lock (_gate)
        {
            _bySource[sourceName] = rows;
            var merged = _bySource.Values.SelectMany(x => x).ToArray();
            var next = merged.ToDictionary(m => m.Id, m => m.ContentFingerprint());
            changed = merged.Where(m => !_fingerprints.TryGetValue(m.Id, out var previous)
                                          || previous != next[m.Id]).ToArray();
            removed = _fingerprints.Keys.Except(next.Keys).ToArray();
            _fingerprints.Clear();
            foreach (var pair in next) _fingerprints[pair.Key] = pair.Value;
        }
        if (changed.Length > 0 || removed.Length > 0)
            SnapshotChanged?.Invoke(changed, removed);
    }

    public async ValueTask DisposeAsync()
    {
        _stop.Cancel();
        RefreshNow();
        try { await Task.WhenAll(_loops).ConfigureAwait(false); }
        catch (OperationCanceledException) { }
        foreach (var wake in _wakes.Values) wake.Dispose();
        _stop.Dispose();
    }
}
