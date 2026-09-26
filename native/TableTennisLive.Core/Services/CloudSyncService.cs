namespace TableTennisLive.Core.Services;

/// <summary>Serialized, offline-safe account operations; callers decide when to refresh the UI.</summary>
public sealed class CloudSyncService(FavoriteStore favorites) : IDisposable
{
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly CloudSessionStore _store = new();
    private CloudApi? _api = CloudConfig.Load() is { } config ? new CloudApi(config) : null;
    private CloudSession? _session;

    public bool Configured => _api is not null;
    public bool SignedIn => _session is not null;
    public string Email => _session?.Email ?? "";
    public string LastSyncError { get; private set; } = "";

    public void Configure(string address, string key)
    {
        if (SignedIn) throw new InvalidOperationException("请先退出当前账号再更换云端项目");
        var config = CloudConfig.Create(address, key);
        config.Save();
        _api?.Dispose();
        _api = new CloudApi(config);
    }

    public async Task<bool> RestoreAsync(CancellationToken ct)
    {
        if (_api is null || _store.LoadRefreshToken() is not { } token) return false;
        await _gate.WaitAsync(ct);
        try
        {
            _session = await _api.RefreshAsync(token, ct);
            _store.Save(_session);
            favorites.ActivateAccount(_session.UserId);
            await SyncCoreAsync(ct);
            return true;
        }
        finally { _gate.Release(); }
    }

    public async Task<bool> SignInAsync(string email, string password,
        bool createAccount, CancellationToken ct)
    {
        if (_api is null) throw new InvalidOperationException("请先连接 Supabase 项目");
        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
            throw new ArgumentException("请输入邮箱和密码");
        await _gate.WaitAsync(ct);
        try
        {
            var session = createAccount
                ? await _api.SignUpAsync(email, password, ct)
                : await _api.SignInAsync(email, password, ct);
            if (session is null) return false; // Email confirmation is pending.
            _session = session;
            _store.Save(session);
            favorites.ActivateAccount(session.UserId);
            LastSyncError = "";
            try { await SyncCoreAsync(ct); }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
            catch (Exception error) { LastSyncError = error.Message; }
            return true;
        }
        finally { _gate.Release(); }
    }

    public async Task SyncAsync(CancellationToken ct)
    {
        if (_api is null || _session is null) return;
        await _gate.WaitAsync(ct);
        try { await SyncCoreAsync(ct); }
        finally { _gate.Release(); }
    }

    private async Task SyncCoreAsync(CancellationToken ct)
    {
        if (_api is null || _session is null) return;
        if (_session.ExpiresAt <= DateTimeOffset.UtcNow.AddMinutes(2))
        {
            _session = await _api.RefreshAsync(_session.RefreshToken, ct);
            _store.Save(_session);
        }
        var sent = favorites.Pending.ToDictionary(row => row.Key, row => row.Value);
        await _api.PushAsync(_session, sent, ct);
        var remote = await _api.FavoritesAsync(_session, ct);
        favorites.Acknowledge(sent);
        favorites.ApplyRemote(remote);
    }

    public async Task SignOutAsync(CancellationToken ct)
    {
        await _gate.WaitAsync(ct);
        try
        {
            _session = null;
            _store.Clear();
            favorites.ActivateAccount(null);
        }
        finally { _gate.Release(); }
    }

    public void Dispose()
    {
        _api?.Dispose();
        _gate.Dispose();
    }
}
