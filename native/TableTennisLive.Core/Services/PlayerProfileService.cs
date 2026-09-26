using System.Text.Json;
using System.Text.RegularExpressions;
using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

/// <summary>Resolve identities only when WTT supplies an ID or a unique ranking match.</summary>
public sealed class PlayerProfileService : IDisposable
{
    private const string Details = "https://wtt-web-cms-api-prod.azurewebsites.net/api/cms/GetPlayersDataByID/";
    private const string PortraitDetails = "https://wtt-web-cms-api-prod.azurewebsites.net/api/cms/GetPlayerProfilePicWithIttfId/";
    private readonly OfficialJson _json = new();
    private readonly Dictionary<string, (PlayerProfile Profile, DateTimeOffset Time)> _cache = [];

    public static string? ResolveId(string name, string raw, string country,
        string suppliedId, IReadOnlyList<RankingEntry> ranking)
    {
        if (ValidId(suppliedId)) return suppliedId;
        var search = Key(raw.Length > 0 ? raw : name);
        var displayed = ChineseNames.Display(name);
        var found = ranking.SelectMany(row => row.IsPair
                ? new[] { (Name: row.PlayerName, Id: row.PlayerId, Country: row.CountryCode),
                    (Name: row.PartnerName, Id: row.PartnerId, Country: row.PartnerCountryCode) }
                : new[] { (Name: row.PlayerName, Id: row.PlayerId, Country: row.CountryCode) })
            .Where(player =>
                (search.Length > 0 && Key(player.Name) == search) ||
                (displayed.Length > 0 && ChineseNames.Display(player.Name) == displayed))
            .Where(player => country.Length == 0 ||
                player.Country.Equals(country, StringComparison.OrdinalIgnoreCase))
            .Select(player => player.Id).Where(ValidId).Distinct().ToArray();
        return found.Length == 1 ? found[0] : null;
    }

    private static bool ValidId(string? id) =>
        !string.IsNullOrEmpty(id) && Regex.IsMatch(id, @"^[1-9]\d*$", RegexOptions.CultureInvariant);

    private static string Key(string value)
    {
        value = Regex.Replace(value, @"\s*(\([A-Z]{3}\)|\[\d+\])\s*$", "").Trim();
        return string.Join(' ', Regex.Matches(value.ToLowerInvariant(), @"[a-z0-9]+")
            .Select(match => match.Value).OrderBy(part => part));
    }

    public async Task<PlayerProfile?> GetAsync(string id, RankingEntry? ranking,
        CancellationToken ct)
    {
        if (!ValidId(id)) return null;
        if (_cache.TryGetValue(id, out var cached) &&
            DateTimeOffset.UtcNow - cached.Time < TimeSpan.FromMinutes(15))
            return cached.Profile;
        var payload = await _json.GetAsync(Details + id, "player-" + id,
            TimeSpan.FromMinutes(15), ct).ConfigureAwait(false);
        var profile = Parse(payload, id, ranking);
        if (profile is not null) _cache[id] = (profile, DateTimeOffset.UtcNow);
        return profile;
    }

    public async Task<Uri?> GetPortraitAsync(string id, CancellationToken ct)
    {
        if (!ValidId(id)) return null;
        var payload = await _json.GetAsync(PortraitDetails + id, "portrait-" + id,
            TimeSpan.FromHours(1), ct).ConfigureAwait(false);
        return TrustedPortrait(payload.At("headShot").Text());
    }

    private static Uri? TrustedPortrait(string url) =>
        Uri.TryCreate(url, UriKind.Absolute, out var image) &&
        image.Scheme == Uri.UriSchemeHttps && image.Host == "wttsimfiles.blob.core.windows.net"
            ? image : null;

    public static PlayerProfile? Parse(JsonElement payload, string id, RankingEntry? ranking)
    {
        var extra = payload.At("additional_data");
        var players = extra.At("PlayerData");
        var row = players.ValueKind == JsonValueKind.Array
            ? players.Items().FirstOrDefault(p => p.At("IttfId").Text() == id)
            : players.At("IttfId").Text() == id ? players : default;
        if (row.ValueKind != JsonValueKind.Object) return null;
        var stats = extra.At("StatsData");
        var eventCode = row.At("Gender").Text() == "F" ? "WS" : "MS";
        var stat = stats.Items().FirstOrDefault(s => s.At("IttfId").Text() == id &&
            s.At("SubeventCode").Text() == eventCode);
        var wins = stat.At("current_year_total_wins").Number();
        var matches = stat.At("current_year_total_matches").Number();
        var photo = row.At("HeadShot").Text();
        if (photo.Length == 0) photo = row.At("HeadshotR").Text();
        Uri? portrait = TrustedPortrait(photo);
        var name = row.At("PlayerName").Text();
        if (name.Length == 0) name = ranking?.PlayerName ?? "";
        var seniorSingles = ranking is { CategoryCode: "SEN", EventCode: "MS" or "WS" };
        return new(id, name, row.At("CountryCode").Text(), row.At("CountryName").Text(),
            seniorSingles ? ranking!.Rank : null,
            seniorSingles ? ranking!.Points : null,
            row.At("Age").Number() is var age && age > 0 ? age : null,
            row.At("Handedness").Text(), matches > 0 ? (int)Math.Round(wins * 100.0 / matches) : null,
            portrait, row.At("Bio").Text(),
            new Uri($"https://www.worldtabletennis.com/playerDescription?playerId={id}"))
        {
            YearWins = matches > 0 ? wins : null,
            YearMatches = matches > 0 ? matches : null
        };
    }

    public void Dispose() => _json.Dispose();
}
