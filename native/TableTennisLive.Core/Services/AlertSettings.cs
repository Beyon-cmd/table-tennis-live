using System.Text.Json;

namespace TableTennisLive.Core.Services;

public sealed class AlertSettings
{
    private readonly string _path;
    private readonly Dictionary<string, bool> _alerts = [];

    public AlertSettings(string? dataDirectory = null)
    {
        var directory = dataDirectory ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "TableTennisLive");
        _path = Path.Combine(directory, "settings.json");
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(_path));
            var values = document.RootElement.At("alerts");
            foreach (var kind in new[] { "start", "score", "final" })
                _alerts[kind] = values.At(kind).Flag();
        }
        catch (Exception error) when (error is IOException or JsonException or UnauthorizedAccessException)
        {
            // A missing or malformed setting is off, never opt-in automatically.
        }
    }

    public bool Enabled(string kind) => _alerts.GetValueOrDefault(kind);

    public void Set(string kind, bool enabled)
    {
        if (kind is not ("start" or "score" or "final"))
            throw new ArgumentException("未知提醒类别", nameof(kind));
        _alerts[kind] = enabled;
        Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
        Dictionary<string, JsonElement> settings;
        try { settings = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(
            File.ReadAllText(_path)) ?? []; }
        catch (Exception error) when (error is IOException or JsonException) { settings = []; }
        settings["alerts"] = JsonSerializer.SerializeToElement(_alerts);
        var temp = _path + ".tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(settings));
        File.Move(temp, _path, overwrite: true);
    }
}
