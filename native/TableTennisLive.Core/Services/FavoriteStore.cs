using System.Text.Json;

namespace TableTennisLive.Core.Services;

/// <summary>Reads the existing Python version's favorites.json in-place.</summary>
public sealed class FavoriteStore
{
    private readonly string _directory;
    private string _path;
    private HashSet<string> _ids;
    private Dictionary<string, bool> _pending = [];
    private string? _userId;

    public FavoriteStore(string? dataDirectory = null)
    {
        _directory = dataDirectory ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "TableTennisLive");
        _path = Path.Combine(_directory, "favorites.json");
        _ids = ReadIds(_path);
    }

    private static HashSet<string> ReadIds(string path)
    {
        try
        {
            return JsonSerializer.Deserialize<HashSet<string>>(File.ReadAllText(path)) ?? [];
        }
        catch (Exception ex) when (ex is IOException or JsonException or UnauthorizedAccessException)
        {
            return [];
        }
    }

    public bool Contains(string id) => _ids.Contains(id);
    public IReadOnlyCollection<string> Ids => _ids;
    public IReadOnlyDictionary<string, bool> Pending => _pending;

    public void ActivateAccount(string? userId)
    {
        if (userId is null)
        {
            _userId = null;
            _path = Path.Combine(_directory, "favorites.json");
            _ids = ReadIds(_path);
            _pending = [];
            return;
        }
        if (!Guid.TryParse(userId, out var parsed))
            throw new ArgumentException("无效的账号标识", nameof(userId));
        _userId = parsed.ToString();
        _path = Path.Combine(_directory, $"favorites-{_userId}.json");
        var pendingPath = PendingPath();
        _pending = ReadPending(pendingPath);
        var firstLogin = !File.Exists(_path);
        _ids = ReadIds(_path);
        if (!firstLogin) return;
        foreach (var id in ReadIds(Path.Combine(_directory, "favorites.json")))
        {
            _ids.Add(id);
            _pending[id] = true;
        }
        Save();
        SavePending();
    }

    public bool Toggle(string id)
    {
        if (!_ids.Add(id)) _ids.Remove(id);
        Save();
        if (_userId is not null)
        {
            _pending[id] = _ids.Contains(id);
            SavePending();
        }
        return _ids.Contains(id);
    }

    public void Acknowledge(IReadOnlyDictionary<string, bool> sent)
    {
        foreach (var (id, value) in sent)
            if (_pending.TryGetValue(id, out var latest) && latest == value)
                _pending.Remove(id);
        SavePending();
    }

    public void ApplyRemote(IReadOnlyCollection<string> remote)
    {
        if (_userId is null) return;
        _ids = remote.ToHashSet(StringComparer.Ordinal);
        foreach (var (id, enabled) in _pending)
        {
            if (enabled) _ids.Add(id);
            else _ids.Remove(id);
        }
        Save();
    }

    private string PendingPath() => Path.Combine(_directory,
        $"favorites-pending-{_userId}.json");

    private static Dictionary<string, bool> ReadPending(string path)
    {
        try
        {
            return JsonSerializer.Deserialize<Dictionary<string, bool>>(File.ReadAllText(path)) ?? [];
        }
        catch (Exception error) when (error is IOException or JsonException or UnauthorizedAccessException)
        {
            return [];
        }
    }

    private void SavePending()
    {
        if (_userId is null) return;
        Directory.CreateDirectory(_directory);
        var path = PendingPath();
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(_pending));
        File.Move(temporary, path, true);
    }

    private void Save()
    {
        var directory = Path.GetDirectoryName(_path)!;
        Directory.CreateDirectory(directory);
        var temporary = _path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(_ids.OrderBy(x => x).ToArray(),
            new JsonSerializerOptions { WriteIndented = true }));
        File.Move(temporary, _path, overwrite: true);
    }
}
