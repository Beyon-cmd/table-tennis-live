using System.Text.Json;
using System.Text.RegularExpressions;

namespace TableTennisLive.Core.Services;

public static class ChineseNames
{
    private static readonly Lazy<(Dictionary<string, string> Players, Dictionary<string, string> Teams)> Maps =
        new(Load);

    public static string Display(string original)
    {
        if (original.Length == 0) return original;
        var country = Regex.Match(original, @"\s*\(([A-Z]{3})\)$");
        var baseName = country.Success ? original[..country.Index].Trim() : original.Trim();
        var chinese = Team(baseName) ?? Player(baseName);
        return chinese is null ? original : chinese + (country.Success ? " " + country.Value.Trim() : "");
    }

    public static string? Player(string name)
    {
        var key = Normalize(name);
        if (key.Length == 0) return null;
        if (Maps.Value.Players.TryGetValue(key, out var direct)) return direct;
        if (!key.Contains('/'))
        {
            var words = key.Split(' ');
            var candidates = new HashSet<string>();
            for (var i = 1; i < words.Length; i++)
            {
                var shifted = string.Join(' ', words[i..].Concat(words[..i]));
                if (Maps.Value.Players.TryGetValue(shifted, out var value)) candidates.Add(value);
            }
            return candidates.Count == 1 ? candidates.Single() : null;
        }
        var parts = name.Split('/', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        var mapped = parts.Select(Player).ToArray();
        return mapped.Length > 1 && mapped.All(x => x is not null)
            ? string.Join(" / ", mapped!) : null;
    }

    public static string? Team(string name) =>
        Maps.Value.Teams.TryGetValue(Normalize(name), out var found) ? found : null;

    private static string Normalize(string value) =>
        string.Join(' ', value.Trim().ToLowerInvariant().Split(' ', StringSplitOptions.RemoveEmptyEntries));

    private static (Dictionary<string, string>, Dictionary<string, string>) Load()
    {
        var assembly = typeof(ChineseNames).Assembly;
        var resource = assembly.GetManifestResourceNames().Single(x => x.EndsWith("name-map.json"));
        using var stream = assembly.GetManifestResourceStream(resource)!;
        using var document = JsonDocument.Parse(stream);
        return (document.RootElement.GetProperty("names").EnumerateObject()
                .ToDictionary(x => x.Name, x => x.Value.GetString() ?? ""),
            document.RootElement.GetProperty("teams").EnumerateObject()
                .ToDictionary(x => x.Name, x => x.Value.GetString() ?? ""));
    }
}
